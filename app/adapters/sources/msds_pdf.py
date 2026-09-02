"""C9 - MSDS PDF adapter (FR-4).

Targets come from a manifest file rather than a crawl. That is a direct
consequence of BR-04: we do not discover documents by walking a site whose
policy might forbid it. An operator (or the substance ingestion run) writes the
manifest, and every entry names its own source URL.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from app.adapters.sources.http import HttpSourceClient
from app.core.config import Settings
from app.core.errors import PermanentError
from app.core.logging import get_logger
from app.core.types import RawDocument, SourceRef

log = get_logger(__name__)


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


class MsdsPdfAdapter:
    def __init__(self, settings: Settings, spec: dict[str, Any]) -> None:
        self._settings = settings
        self._spec = spec
        self._client = HttpSourceClient(settings, spec["base_url"], timeout=60.0)
        self._manifest_path = Path(spec.get("manifest_path", "config/msds_manifest.json"))

    def source_id(self) -> str:
        return str(self._spec["source_id"])

    def _load_manifest(self) -> list[dict[str, Any]]:
        if not self._manifest_path.exists():
            log.warning(
                "msds_manifest_missing", extra={"path": str(self._manifest_path)}
            )
            return []
        try:
            data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PermanentError(
                f"MSDS manifest is not valid JSON: {self._manifest_path}", detail=str(exc)
            ) from exc
        documents = data.get("documents", [])
        if not isinstance(documents, list):
            raise PermanentError("MSDS manifest 'documents' must be a list")
        return documents

    def list_targets(self, since: datetime | None) -> Iterator[SourceRef]:
        for entry in self._load_manifest():
            url = entry.get("url")
            external_id = entry.get("id") or url
            if not url or not external_id:
                # BR-32 - an entry with no traceable URL is skipped outright.
                log.warning("msds_manifest_entry_missing_url", extra={"entry": entry})
                continue
            published = _parse_date(entry.get("published_at"))
            if since and published and published < since:
                continue
            yield SourceRef(
                source_id=self.source_id(),
                external_id=str(external_id),
                url=str(url),
                published_at=published,
                revised_at=_parse_date(entry.get("revised_at")),
                # No hash yet - it is computed from the downloaded bytes (BR-09).
                content_hash=None,
                extra={
                    "title": entry.get("title"),
                    "cas_number": entry.get("cas_number"),
                },
            )

    def fetch(self, ref: SourceRef) -> RawDocument:
        content = self._client.get_bytes(ref.url)
        if not content:
            raise PermanentError("empty PDF response", detail=ref.url)
        if not content.startswith(b"%PDF"):
            raise PermanentError(
                "response is not a PDF", detail=f"{ref.url} starts with {content[:8]!r}"
            )
        digest = hashlib.sha256(content).hexdigest()
        return RawDocument(
            ref=SourceRef(
                source_id=ref.source_id,
                external_id=ref.external_id,
                url=ref.url,
                published_at=ref.published_at,
                revised_at=ref.revised_at,
                content_hash=digest,
                extra=ref.extra,
            ),
            content=content,
            media_type="application/pdf",
        )
