"""Shared HTTP plumbing for source adapters.

Every network failure is translated into a `TransientError` or `PermanentError`
so that `RetryPolicy` can classify it without knowing anything about httpx
(BR-41, BR-42).
"""

from __future__ import annotations

import time
from typing import Any
from xml.etree import ElementTree

import httpx

from app.core.config import Settings
from app.core.errors import (
    ApiKeyMissingError,
    FailureKind,
    SchemaMismatchError,
    SourceNotFoundError,
    SourceUnavailableError,
    classify_http_status,
)
from app.core.logging import get_logger

log = get_logger(__name__)


class HttpSourceClient:
    """Thin wrapper that enforces the inter-request interval (BR-06) and turns
    HTTP status codes into classified errors."""

    def __init__(self, settings: Settings, base_url: str, timeout: float = 30.0) -> None:
        self._settings = settings
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._last_request_at = 0.0

    def _respect_interval(self) -> None:
        """BR-06 - never hammer a public API."""
        interval = self._settings.request_interval_ms / 1000.0
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last_request_at = time.monotonic()

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return the response body as a dict, whether it arrived as JSON or XML.

        Korean public APIs answer in XML unless asked otherwise, and not all of
        them accept a format parameter - the 화학사고정보 service documents only
        ServiceKey/pageNo/numOfRows/yyyy. Treating an XML body as a hard failure
        would have made a correctly-issued key look broken, so the body is
        converted instead. The adapters then read either shape identically.
        """
        response = self._request(path, params)
        body = response.text.lstrip()
        if body.startswith("<"):
            return self._xml_to_dict(body, path)
        try:
            payload = response.json()
        except ValueError as exc:
            raise SchemaMismatchError(
                f"source returned neither JSON nor XML for {path}",
                detail=f"{str(exc)}; body starts with {body[:80]!r}",
            ) from exc
        if not isinstance(payload, dict):
            return {"response": payload}
        return payload

    @staticmethod
    def _xml_to_dict(body: str, path: str) -> dict[str, Any]:
        try:
            root = ElementTree.fromstring(body)
        except ElementTree.ParseError as exc:
            raise SchemaMismatchError(
                f"source returned malformed XML for {path}", detail=str(exc)
            ) from exc
        return {root.tag: _element_to_value(root)}

    def get_bytes(self, path_or_url: str, params: dict[str, Any] | None = None) -> bytes:
        return self._request(path_or_url, params).content

    def _request(self, path_or_url: str, params: dict[str, Any] | None) -> httpx.Response:
        url = (
            path_or_url
            if path_or_url.startswith("http")
            else f"{self._base_url}/{path_or_url.lstrip('/')}"
        )
        self._respect_interval()
        try:
            response = httpx.get(
                url, params=params, timeout=self._timeout, follow_redirects=True
            )
        except httpx.TimeoutException as exc:
            raise SourceUnavailableError(f"timeout fetching {url}", detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise SourceUnavailableError(f"network error fetching {url}", detail=str(exc)) from exc

        if response.status_code >= 400:
            kind = classify_http_status(response.status_code)
            message = f"HTTP {response.status_code} from source"
            # BR-07 - honour Retry-After when the source asks us to back off.
            retry_after = response.headers.get("Retry-After")
            if kind is FailureKind.TRANSIENT:
                raise SourceUnavailableError(message, detail=f"retry_after={retry_after}")
            # data.go.kr answers an unapproved key with 403 and an XML body that
            # says exactly what is wrong ("등록되지 않은 서비스키"). Reporting only
            # the status code threw that away and left the operator guessing
            # whether the key, the endpoint or the service was at fault.
            raise SourceNotFoundError(message, detail=_error_detail(response, url))

        return response


def _error_detail(response: httpx.Response, url: str) -> str:
    """Include the source's own explanation when it sent one."""
    body = (response.text or "").strip()
    if not body:
        return url
    for tag in ("returnAuthMsg", "errMsg", "resultMsg", "returnReasonCode"):
        marker = f"<{tag}>"
        if marker in body:
            start = body.index(marker) + len(marker)
            end = body.find(f"</{tag}>", start)
            if end != -1:
                return f"{url} :: {tag}={body[start:end].strip()!r}"
    return f"{url} :: body={body[:200]!r}"


def _element_to_value(element: ElementTree.Element) -> Any:
    """Convert an XML element to the same shape a JSON body would have.

    A tag repeated within its parent becomes a list, which is what makes
    `<item>` rows read the same as a JSON `item` array. A tag that appears once
    stays scalar; `_rows` wraps a lone dict, so a single-row response is not a
    special case for callers.
    """
    children = list(element)
    if not children:
        return (element.text or "").strip()
    out: dict[str, Any] = {}
    for child in children:
        value = _element_to_value(child)
        if child.tag in out:
            existing = out[child.tag]
            if isinstance(existing, list):
                existing.append(value)
            else:
                out[child.tag] = [existing, value]
        else:
            out[child.tag] = value
    return out


def resolve_api_key(settings: Settings, api_key_env: str | None, source_id: str) -> str | None:
    """BR-02 - a missing key fails this source only; the app still starts and
    other sources still run."""
    if not api_key_env:
        return None
    key = settings.api_key_for(api_key_env)
    if not key:
        raise ApiKeyMissingError(
            f"source '{source_id}' requires {api_key_env}, which is not set",
            detail=f"set {api_key_env} in .env",
        )
    return key
