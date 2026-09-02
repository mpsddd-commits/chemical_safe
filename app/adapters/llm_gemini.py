"""Google Gemini adapter (NFR-21).

The port existed before either implementation did, which is the point: swapping
providers is an adapter, not a rewrite. Nothing in `rag/` knows this file exists.

Three differences from the Anthropic adapter are worth stating, because each one
is a rule that has to be honoured differently rather than dropped.

  * **Schema dialect.** Gemini takes an OpenAPI 3.0 subset and rejects
    `additionalProperties`. `schema_guard.to_gemini_schema` translates, and
    `schema_guard.validate` re-checks on our side what the provider no longer
    enforces (BR-79).
  * **Caching.** There is no per-block `cache_control`. Gemini caches implicitly
    on a stable prefix, so BR-94's layout - fixed system instruction first,
    question last - is what makes it work, and `cached_content_token_count` is
    how PP-4 sees whether it did.
  * **Refusal.** There is no `stop_reason="refusal"`. A blocked response arrives
    as an empty candidate with a `finish_reason` such as `SAFETY`, mapped to the
    same `ProviderRefusal` so BR-77 does not care which provider ran.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.adapters.llm_anthropic import ProviderRefusal
from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError, QuotaExhaustedError
from app.core.logging import get_logger
from app.ports.llm import LLMResult
from app.rag.schema_guard import to_gemini_schema

log = get_logger(__name__)

PROVIDER = "gemini"
DEFAULT_MODEL = "gemini-3.1-flash-lite"

# The API rejects a shorter deadline outright:
#   400 INVALID_ARGUMENT - "Manually set deadline 8s is too short.
#                           Minimum allowed deadline is 10s"
# Discovered 2026-08-26 when `VERIFY_LLM_TIMEOUT_SECONDS=8` made *every*
# verification call fail, which BR-87 then correctly turned into `unverified`
# and removed - so a config value silently emptied every answer.
_MIN_TIMEOUT_SECONDS = 10.0

# finish_reason values that mean "the model declined", not "the call failed".
# Retrying any of these repeats the decision (BR-77).
_REFUSAL_REASONS = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "RECITATION"}


class GeminiLLMAdapter:
    def __init__(self, settings: Settings | None = None, model: str | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = model or self._settings.resolved_llm_model
        self._client: Any = None
        # Stage-two verification runs this adapter from a thread pool (PP-5), so
        # the lazy init below is entered concurrently. Without the lock two
        # threads each built a client, one assignment won, and the loser's
        # client was collected out from under the thread still using it:
        # "Cannot send a request, as the client has been closed" - 3 of 8
        # verification calls, measured 2026-08-26. BR-87 then correctly removed
        # those sentences, so a race looked like an evidence problem.
        self._client_lock = threading.Lock()

    @property
    def model(self) -> str:
        return self._model

    def _require_key(self) -> str:
        key = self._settings.gemini_api_key.get_secret_value()
        if not key:
            # BR-02 - the app still starts; only querying is unavailable.
            raise ConfigurationError(
                "GEMINI_API_KEY is not set. It is required when LLM_PROVIDER=gemini."
            )
        return key

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        with self._client_lock:
            if self._client is not None:
                return self._client
            from google import genai
            from google.genai import types

            # The timeout has to be passed here. Without it the SDK waits on its
            # own default, and `entity_llm_timeout_seconds` - the whole point of
            # giving the optional extraction step a short leash - does nothing.
            # Measured 2026-08-25: retrieval ran 18.3s against a 2.5s budget
            # because this argument was missing. `timeout` is milliseconds.
            timeout_s = self._settings.llm_timeout_seconds
            if timeout_s < _MIN_TIMEOUT_SECONDS:  # noqa: SIM102
                # Clamped, and said out loud. A shorter leash is simply not
                # available here, and silently accepting the setting would leave
                # `entity_llm_timeout_seconds=2` looking effective while the
                # provider ignored it - or, as measured, returned 400 on every
                # call.
                log.warning(
                    "llm_timeout_below_provider_minimum",
                    extra={
                        "requested_s": timeout_s,
                        "applied_s": _MIN_TIMEOUT_SECONDS,
                        "provider": PROVIDER,
                    },
                )
                timeout_s = _MIN_TIMEOUT_SECONDS
            self._client = genai.Client(
                api_key=self._require_key(),
                http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
            )
        return self._client

    def _config(self, system: str | None, schema: dict | None) -> Any:
        from google.genai import types

        kwargs: dict[str, Any] = {}
        if system:
            # BR-94 - the fixed instruction is the cache prefix. Gemini caches
            # implicitly on a stable prefix rather than on an explicit marker,
            # so the layout is the whole mechanism here.
            kwargs["system_instruction"] = system
        if schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_schema"] = to_gemini_schema(schema)
        return types.GenerateContentConfig(**kwargs)

    # ---- retry classification (FQ3-14) ----

    def _call_with_retry(self, operation):
        transient_left = self._settings.llm_max_retries
        rate_left = self._settings.llm_rate_limit_retries

        while True:
            try:
                return operation()
            except Exception as exc:  # noqa: BLE001 - classified below, then re-raised
                status = _status_of(exc)
                if status == 429:
                    delay = _retry_after(exc, default=2.0)
                    if rate_left <= 0 or delay > self._settings.max_retry_after_seconds:
                        # Waiting this long would blow NFR-1 and end in the same
                        # failure. Fail now, and as the condition it actually is.
                        log.warning(
                            "llm_quota_exhausted",
                            extra={
                                "provider": PROVIDER,
                                "model": self._model,
                                "retry_after_s": delay,
                            },
                        )
                        raise QuotaExhaustedError(
                            f"{PROVIDER} quota exhausted for {self._model}",
                            retry_after_seconds=delay,
                        ) from exc
                    rate_left -= 1
                    log.warning(
                        "llm_rate_limited", extra={"provider": PROVIDER, "sleep_s": delay}
                    )
                    time.sleep(delay)
                    continue
                if status in (500, 502, 503, 504) and transient_left > 0:
                    transient_left -= 1
                    log.warning("llm_transient_retry", extra={"error": str(exc)[:200]})
                    time.sleep(1.0)
                    continue
                # 4xx other than 429, and everything else: the request is wrong,
                # not unlucky.
                raise

    # ---- port surface ----

    def generate(self, prompt: str, system: str | None = None) -> tuple[str, LLMResult]:
        started = time.perf_counter()
        response = self._call_with_retry(
            lambda: self._get_client().models.generate_content(
                model=self._model, contents=prompt, config=self._config(system, None)
            )
        )
        result = _to_result(self._model, response, started)
        _raise_if_refused(self._model, response, result)
        return response.text or "", result

    def generate_structured(
        self, prompt: str, schema: dict[str, Any], system: str | None = None
    ) -> tuple[dict[str, Any], LLMResult]:
        started = time.perf_counter()
        response = self._call_with_retry(
            lambda: self._get_client().models.generate_content(
                model=self._model, contents=prompt, config=self._config(system, schema)
            )
        )
        result = _to_result(self._model, response, started)
        _raise_if_refused(self._model, response, result)
        return _parse(response.text), result

    def stream_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
        on_delta: Any = None,
    ) -> tuple[dict[str, Any], LLMResult]:
        """As `generate_structured`, with progress callbacks (FQ2-13).

        The deltas are partial JSON, not prose - `rag.streaming` turns them into
        sentence text for display. The **return value is parsed from the whole
        document**, so nothing that streamed is treated as an answer before the
        id whitelist (SP-8) has seen it.
        """
        started = time.perf_counter()
        buffer: list[str] = []
        last: Any = None

        def run():
            nonlocal last
            buffer.clear()
            stream = self._get_client().models.generate_content_stream(
                model=self._model, contents=prompt, config=self._config(system, schema)
            )
            for chunk in stream:
                text = getattr(chunk, "text", None)
                if not text:
                    continue
                buffer.append(text)
                if on_delta is not None:
                    on_delta(text)
                last = chunk
            return last

        response = self._call_with_retry(run)
        result = _to_result(self._model, response, started)
        if response is not None:
            _raise_if_refused(self._model, response, result)
        return _parse("".join(buffer)), result


# ---- helpers ----


def _status_of(exc: Exception) -> int | None:
    for attribute in ("code", "status_code"):
        value = getattr(exc, attribute, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _retry_after(exc: Exception, default: float) -> float:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _raise_if_refused(model: str, response: Any, result: LLMResult) -> None:
    """BR-77 - a decline is a terminal outcome, not a fault to retry."""
    for candidate in getattr(response, "candidates", None) or []:
        reason = getattr(candidate, "finish_reason", None)
        name = getattr(reason, "name", None) or str(reason or "")
        if name.upper() in _REFUSAL_REASONS:
            raise ProviderRefusal(model, result)
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        raise ProviderRefusal(model, result)


def _to_result(model: str, response: Any, started: float) -> LLMResult:
    usage = getattr(response, "usage_metadata", None)
    return LLMResult(
        model=model,
        input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
        output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        latency_ms=(time.perf_counter() - started) * 1000,
        ok=True,
    )


def cache_read_tokens(response: Any) -> int:
    """PP-4 - implicit caching still reports what it reused."""
    usage = getattr(response, "usage_metadata", None)
    return getattr(usage, "cached_content_token_count", 0) or 0


def _parse(text: str | None) -> dict[str, Any]:
    if not text:
        # An empty body with no refusal marker is a malformed response, and the
        # caller's schema check turns it into one retry (BR-80).
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("gemini_unparseable_json", extra={"head": text[:200]})
        return {}
