"""C9 - SourceAdapter implementations for the three API-backed corpora.

All three share one shape because `sources.yaml` carries the endpoint paths, the
auth parameter name and the field names (risk R-1: the real contracts could not
be verified without issued keys). Correcting any of them is a config edit, not a
code change - which is what allowed the 화학사고 source to be repointed once it
turned out that the configured endpoint did not exist and therefore no issued
key could ever have worked against it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from app.adapters.sources.http import HttpSourceClient, resolve_api_key
from app.core.config import Settings
from app.core.errors import (
    ApiKeyMissingError,
    SchemaMismatchError,
    SourceUnavailableError,
)
from app.core.logging import get_logger
from app.core.types import RawDocument, SourceRef
from app.ingestion import substance_selection

log = get_logger(__name__)

# data.go.kr answers an unusable credential with HTTP 200 and an error envelope.
# Without this table the failure surfaced as "no item list in response", which
# says nothing about the actual cause - the key is unregistered, expired, or the
# service was never approved for this account.
_AUTH_FAILURE_CODES = {
    "20": "SERVICE_ACCESS_DENIED - 활용신청이 승인되지 않았습니다",
    "30": "SERVICE_KEY_IS_NOT_REGISTERED - 등록되지 않은 인증키입니다",
    "31": "DEADLINE_HAS_EXPIRED - 인증키 활용기간이 만료되었습니다",
    "32": "UNREGISTERED_IP - 등록되지 않은 IP 입니다",
}
_QUOTA_FAILURE_CODES = {
    "22": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS - 일일 트래픽을 초과했습니다",
}
_OK_CODES = {"00", "0", "000"}


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace(".", "-").replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[: len(fmt) + 2].strip(), fmt)
        except ValueError:
            continue
    return None


def _hash_payload(payload: dict[str, Any]) -> str:
    """BR-09 - content hash is the primary change signal."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dig(payload: Any, key: str, depth: int = 6) -> Any:
    """Find `key` anywhere in a nested response.

    data.go.kr wraps rows in response -> body -> items -> item, but the depth
    differs between services and the XML-converted form adds another level. The
    original two-level peek missed the standard envelope entirely, so this walks
    the structure instead of guessing where to look.
    """
    if depth < 0:
        return None
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _dig(value, key, depth - 1)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _dig(value, key, depth - 1)
            if found is not None:
                return found
    return None


def _result_code(payload: Any) -> str | None:
    for key in ("resultCode", "returnReasonCode", "errorCode"):
        code = _dig(payload, key)
        if code not in (None, ""):
            return str(code).strip()
    return None


def _result_message(payload: Any) -> str:
    for key in ("resultMsg", "returnAuthMsg", "errMsg", "errorMsg"):
        message = _dig(payload, key)
        if message not in (None, ""):
            return str(message).strip()
    return ""


def raise_for_service_error(payload: Any, source_id: str, api_key_env: str | None) -> None:
    """Turn a 200-with-error-body into an error that names the real problem.

    The credential problems are `permanent` on purpose: retrying an unregistered
    key produces the same answer, and the operator has to act (BR-42). A quota
    breach is transient - tomorrow it works (BR-41).
    """
    code = _result_code(payload)
    if code is None or code in _OK_CODES:
        return
    message = _result_message(payload)
    if code in _AUTH_FAILURE_CODES:
        env_hint = f"{api_key_env} 환경변수" if api_key_env else "인증키"
        raise ApiKeyMissingError(
            f"source '{source_id}': {_AUTH_FAILURE_CODES[code]}",
            detail=f"resultCode={code} msg={message!r}; {env_hint}와 활용신청 상태를 확인하세요",
        )
    if code in _QUOTA_FAILURE_CODES:
        raise SourceUnavailableError(
            f"source '{source_id}': {_QUOTA_FAILURE_CODES[code]}",
            detail=f"resultCode={code} msg={message!r}",
        )
    raise SchemaMismatchError(
        f"source '{source_id}' returned an error result",
        detail=f"resultCode={code} msg={message!r}",
    )


class ConfiguredApiAdapter:
    """Base for the JSON/XML API sources."""

    def __init__(self, settings: Settings, spec: dict[str, Any]) -> None:
        self._settings = settings
        self._spec = spec
        self._client = HttpSourceClient(settings, spec["base_url"])
        self._field_map: dict[str, str] = spec.get("field_map", {})

    def source_id(self) -> str:
        return str(self._spec["source_id"])

    @property
    def doc_type(self) -> str:
        return str(self._spec["doc_type"])

    def _auth_params(self) -> dict[str, Any]:
        """The parameter name is configuration, not a constant.

        data.go.kr services read `serviceKey` (the 화학사고 service spells it
        `ServiceKey`); 국가법령정보 reads `OC` and expects the ID part of the
        registered e-mail. Assuming `serviceKey` everywhere silently produced
        unauthenticated requests against two of the three sources.
        """
        key = resolve_api_key(self._settings, self._spec.get("api_key_env"), self.source_id())
        if not key:
            return {}
        return {str(self._spec.get("auth_param", "serviceKey")): key}

    def _base_params(self) -> dict[str, Any]:
        params = self._auth_params()
        params.update(self._spec.get("extra_params") or {})
        return params

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = self._client.get_json(path, params)
        raise_for_service_error(payload, self.source_id(), self._spec.get("api_key_env"))
        return payload

    def _rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        # Not every source follows the item/items/row convention: 국가법령정보
        # returns LawSearch.law. The key is therefore configurable, and the
        # conventional names stay as the fallback.
        candidates = [self._spec.get("rows_key"), "item", "items", "row"]
        items = None
        for candidate in candidates:
            if not candidate:
                continue
            items = _dig(payload, str(candidate))
            if items is not None:
                break
        if isinstance(items, dict) and "item" in items:
            items = items["item"]
        if isinstance(items, str) and not items.strip():
            # Exhaustion. Past the last page data.go.kr answers with
            # `"items": ""` instead of an empty list - measured on page 73 of
            # 화학물질안전관리정보 (totalCount 7,189 at page_size 100). Callers read
            # an empty return as "stop", so raising here aborts a full
            # collection at the very end. Nothing had hit it because
            # INITIAL_SUBSTANCE_TARGET always stopped the loop first; BR-08
            # selection scans the whole listing and reaches it every time.
            return []
        if items is None:
            raise SchemaMismatchError(
                f"no item list in response from {self.source_id()}",
                detail=f"top-level keys: {sorted(payload)[:10]}",
            )
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            raise SchemaMismatchError(
                f"item list from {self.source_id()} is not a list",
                detail=f"got {type(items).__name__}",
            )
        return [row for row in items if isinstance(row, dict)]

    def _field(self, row: dict[str, Any], logical: str) -> Any:
        physical = self._field_map.get(logical)
        return row.get(physical) if physical else None

    def _project(self, row: dict[str, Any]) -> dict[str, Any]:
        """Rename the source's physical field names to the logical ones.

        `extract` renders a payload as "key: value" lines and the structurers
        match on those labels, so the label a chunk is found under is decided
        here. Emitting the raw vendor names (`cscDe`, `chem`, `summary`) meant
        the incident structurer recognised nothing, and text outside a section
        is not chunked (BR-26) - the substantive part of the record would have
        been dropped silently.

        Unmapped fields keep their original name rather than being discarded:
        losing a field we did not anticipate is worse than an ugly label.
        """
        inverse: dict[str, str] = {}
        # `external_id` is usually an alias of a field that has a better name
        # (`cas_number`), so it only claims a physical field nothing else wants.
        ordered = [(k, v) for k, v in self._field_map.items() if k != "external_id"]
        ordered += [(k, v) for k, v in self._field_map.items() if k == "external_id"]
        for logical, physical in ordered:
            inverse.setdefault(str(physical), str(logical))
        return {inverse.get(str(key), str(key)): value for key, value in row.items()}

    def _url_for(self, external_id: str) -> str:
        template = self._spec.get("url_template")
        if template:
            return str(template).format(external_id=external_id)
        return f"{self._spec['base_url']}{self._spec.get('detail_path', '')}?id={external_id}"

    def list_targets(self, since: datetime | None) -> Iterator[SourceRef]:
        yield from self._iter_listing(since, self._settings.initial_substance_target)

    def _iter_listing(self, since: datetime | None, limit: int) -> Iterator[SourceRef]:
        """The paging loop, with the cut-off as an argument.

        BR-08 selection has to see more of the listing than it keeps, so the
        limit cannot stay hard-wired to the collection target.
        """
        params = self._base_params()
        params["numOfRows"] = self._spec.get("page_size", 100)
        page = 1
        seen = 0
        # Paging stops when a page is empty, but a source that ignores `pageNo`
        # returns the same page forever - and with a `since` filter rejecting
        # every row, `seen` never advances either, so nothing else would ever
        # end the loop. Identifiers already returned end it instead.
        returned_ids: set[str] = set()
        while seen < limit:
            params["pageNo"] = page
            rows = self._rows(self._get(self._spec["list_path"], params))
            if not rows:
                return
            page_ids = {
                str(self._field(row, "external_id"))
                for row in rows
                if self._field(row, "external_id")
            }
            if page_ids and page_ids <= returned_ids:
                log.warning(
                    "source_paging_not_advancing",
                    extra={
                        "source_id": self.source_id(),
                        "page": page,
                        "impact": "stopped early; the source repeated a page it had already sent",
                    },
                )
                return
            returned_ids |= page_ids
            for row in rows:
                external_id = self._field(row, "external_id")
                if not external_id:
                    continue
                published = _parse_date(self._field(row, "published_at"))
                if since and published and published < since:
                    continue
                yield SourceRef(
                    source_id=self.source_id(),
                    external_id=str(external_id),
                    url=self._url_for(str(external_id)),
                    published_at=published,
                    revised_at=_parse_date(self._field(row, "revised_at")),
                    content_hash=_hash_payload(row),
                    extra={"row": row},
                )
                seen += 1
                if seen >= limit:
                    return
            page += 1

    def fetch(self, ref: SourceRef) -> RawDocument:
        detail_path = self._spec.get("detail_path")
        if not detail_path:
            # Listing already carried the full record (datasets).
            payload = ref.extra.get("row", {})
        else:
            # The detail call does not always take the same parameter as the
            # listing: 국가법령정보 requires an uppercase `ID` plus `target`, and
            # a lowercase `id` simply 404s.
            params = self._base_params()
            params.update(self._spec.get("detail_params") or {})
            params[str(self._spec.get("detail_id_param", "id"))] = ref.external_id
            payload = self._get(detail_path, params)
        return RawDocument(
            ref=ref,
            payload=self._project(payload),
            media_type="application/json",
        )


class SubstanceApiAdapter(ConfiguredApiAdapter):
    """FR-1 - substance master data and GHS classification.

    Also produces the synonym rows that u3 will read (DD-21): they are cheapest
    to capture here, at collection time.

    `priority_terms` implements BR-08. It is set by the caller rather than read
    here because the names come from the corpus already in the database, and a
    source adapter that queries the database stops being a source adapter. Left
    empty - which is what every test and every other caller does - the listing
    is taken in the source's own order, exactly as before.
    """

    def __init__(self, settings: Settings, spec: dict[str, Any]) -> None:
        super().__init__(settings, spec)
        self.priority_terms: tuple[str, ...] = ()

    def list_targets(self, since: datetime | None) -> Iterator[SourceRef]:
        target = self._settings.initial_substance_target
        if not self.priority_terms:
            yield from self._iter_listing(since, target)
            return

        # The whole listing has to be read before any of it can be ranked, so
        # this buffers where the plain path streams. 7,189 rows measured, and
        # the cap is what keeps a source that grows by an order of magnitude
        # from turning a collection into an unbounded scan.
        entries: list[tuple[SourceRef, tuple[str, ...]]] = []
        for ref in self._iter_listing(since, self._settings.substance_scan_cap):
            row = ref.extra.get("row") or {}
            names = tuple(
                str(value)
                for value in (self._field(row, "name_ko"), self._field(row, "name_en"))
                if value
            )
            entries.append((ref, names))

        selected, matched = substance_selection.partition(
            entries, self.priority_terms, target
        )
        log.info(
            "substance_selection",
            extra={
                "source_id": self.source_id(),
                "scanned": len(entries),
                "terms": len(self.priority_terms),
                "matched": matched,
                "selected": len(selected),
            },
        )
        if not matched:
            # Not an error - the corpus may genuinely name nothing the master
            # carries - but it means the selection did nothing, and that is
            # worth saying out loud rather than leaving to be inferred from a
            # disappointing set of cards.
            log.warning(
                "substance_selection_matched_nothing",
                extra={
                    "source_id": self.source_id(),
                    "impact": "collected in source order; cards may have no document behind them",
                },
            )
        yield from selected


class LawApiAdapter(ConfiguredApiAdapter):
    """FR-2 - statute text, later split into articles by the law structurer."""

    def list_targets(self, since: datetime | None) -> Iterator[SourceRef]:
        params = self._base_params()
        params["target"] = "law"
        for law_name in self._spec.get("targets", []):
            params["query"] = law_name
            payload = self._get(self._spec["list_path"], params)
            for row in self._rows(payload):
                external_id = self._field(row, "external_id")
                if not external_id:
                    continue
                yield SourceRef(
                    source_id=self.source_id(),
                    external_id=str(external_id),
                    url=f"{self._spec['base_url']}{self._spec['detail_path']}"
                    f"?target=law&ID={external_id}",
                    published_at=_parse_date(self._field(row, "published_at")),
                    revised_at=_parse_date(self._field(row, "revised_at")),
                    content_hash=_hash_payload(row),
                    extra={"row": row, "law_name": law_name},
                )


class IncidentDataAdapter(ConfiguredApiAdapter):
    """FR-3 - chemical accident records (data.go.kr 15072446).

    These drive the initial substance selection (BR-08): substances that have
    actually been involved in an incident are the ones users ask about.

    The list operation returns the complete record, so `fetch` never issues a
    second request - `sources.yaml` deliberately declares no `detail_path`.
    """

    def fetch(self, ref: SourceRef) -> RawDocument:
        row = ref.extra.get("row") or {}
        if not row:
            raise SchemaMismatchError(
                "incident record carried no row payload", detail=ref.ref_key
            )
        return RawDocument(ref=ref, payload=self._project(row), media_type="application/json")
