"""C10 - Anthropic LLM adapter (FR-18, NFR-21, FQ3-14).

u1 left this raising `NotImplementedError` so the port and its tracing decorator
could be wired identically across units (DD-16, DD-21). This is the u2
implementation.

Three behaviours here are decisions, not defaults:

  * **`stop_reason == "refusal"` is not an error** (BR-77). Treating it as one
    produces a retry loop against a model that has already decided; it maps to
    `RefusalReason.PROVIDER_REFUSAL` and the query ends honestly.
  * **Retries are classified, not counted** (FQ3-14). 5xx and timeouts get one
    attempt; 429 follows `retry-after` up to a separate cap; 4xx and refusals
    get none, because repeating them changes nothing. This mirrors u1's BR-41
    three-way split rather than inventing a second policy.
  * **Token counts come from the response `usage`**, never from
    `processing/tokens.py`. That heuristic exists to size chunks and is not a
    billing unit (W10).
"""

from __future__ import annotations

import time
from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError
from app.core.logging import get_logger
from app.ports.llm import LLMResult

log = get_logger(__name__)

PROVIDER = "anthropic"


class ProviderRefusal(Exception):
    """The model declined. A terminal outcome, not a failure to retry (BR-77)."""

    def __init__(self, model: str, result: LLMResult) -> None:
        super().__init__(f"{model} returned stop_reason=refusal")
        self.result = result


class AnthropicLLMAdapter:
    def __init__(self, settings: Settings | None = None, model: str | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = model or self._settings.resolved_llm_model
        self._client: Any = None

    @property
    def model(self) -> str:
        return self._model

    def _require_key(self) -> str:
        key = self._settings.anthropic_api_key.get_secret_value()
        if not key:
            # BR-02 - the app still starts; only querying is unavailable.
            raise ConfigurationError(
                "ANTHROPIC_API_KEY is not set. It is required from unit u2 onwards."
            )
        return key

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=self._require_key(), timeout=self._settings.llm_timeout_seconds
            )
        return self._client

    # ---- retry classification (FQ3-14) ----

    def _call_with_retry(self, operation):
        import anthropic

        transient_left = self._settings.llm_max_retries
        rate_left = self._settings.llm_rate_limit_retries

        while True:
            try:
                return operation()
            except anthropic.RateLimitError as exc:
                if rate_left <= 0:
                    raise
                delay = _retry_after(exc, default=1.0)
                if delay > self._settings.max_retry_after_seconds:
                    # Sleeping past the answer budget is a hang, not a retry.
                    log.warning("llm_rate_limited_giving_up", extra={"retry_after_s": delay})
                    raise
                rate_left -= 1
                log.warning("llm_rate_limited", extra={"sleep_s": delay})
                time.sleep(delay)
            except (anthropic.APITimeoutError, anthropic.InternalServerError) as exc:
                if transient_left <= 0:
                    raise
                transient_left -= 1
                log.warning("llm_transient_retry", extra={"error": str(exc)})
                time.sleep(1.0)
            except anthropic.APIStatusError:
                # 4xx other than 429: the request is wrong, not unlucky.
                raise

    # ---- port surface ----

    def generate(self, prompt: str, system: str | None = None) -> tuple[str, LLMResult]:
        started = time.perf_counter()
        response = self._call_with_retry(
            lambda: self._get_client().messages.create(
                model=self._model,
                max_tokens=2048,
                system=_system_blocks(system),
                messages=[{"role": "user", "content": prompt}],
            )
        )
        result = _to_result(self._model, response, started)
        if getattr(response, "stop_reason", None) == "refusal":
            raise ProviderRefusal(self._model, result)
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        return text, result

    def generate_structured(
        self, prompt: str, schema: dict[str, Any], system: str | None = None
    ) -> tuple[dict[str, Any], LLMResult]:
        """BR-79 - the schema is enforced by the API, not by parsing hope.

        This is also the strongest injection defence in the system: an
        instruction that hijacks the model still cannot produce anything outside
        the declared shape (SP-1.4).
        """
        started = time.perf_counter()
        response = self._call_with_retry(
            lambda: self._get_client().messages.create(
                model=self._model,
                max_tokens=4096,
                system=_system_blocks(system),
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        )
        result = _to_result(self._model, response, started)
        if getattr(response, "stop_reason", None) == "refusal":
            raise ProviderRefusal(self._model, result)
        payload = _extract_json(response)
        return payload, result


    def stream_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
        on_delta: Any = None,
    ) -> tuple[dict[str, Any], LLMResult]:
        """Same contract as `generate_structured`, with progress callbacks.

        What streams is partial JSON, not prose (BR-79 forces the schema), so
        `on_delta` receives raw fragments and `rag.streaming` turns them into
        sentence text for display. The **return value is parsed from the
        complete document**: nothing that streamed is treated as an answer until
        the whole thing has arrived and passed the id whitelist (SP-8).
        """
        import json

        started = time.perf_counter()
        buffer: list[str] = []

        def run():
            client = self._get_client()
            with client.messages.stream(
                model=self._model,
                max_tokens=4096,
                system=_system_blocks(system),
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            ) as stream:
                for text in stream.text_stream:
                    buffer.append(text)
                    if on_delta is not None:
                        on_delta(text)
                return stream.get_final_message()

        response = self._call_with_retry(run)
        result = _to_result(self._model, response, started)
        if getattr(response, "stop_reason", None) == "refusal":
            raise ProviderRefusal(self._model, result)
        try:
            payload = _extract_json(response)
        except (ValueError, TypeError):
            payload = json.loads("".join(buffer))
        return payload, result


def _system_blocks(system: str | None) -> Any:
    """BR-94 - the system prompt is the cache prefix, so it is marked as one.

    The question and the evidence sit in the user turn and change every request;
    if they were part of the prefix the cache would never hit.
    """
    if not system:
        return []
    return [
        {
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _retry_after(exc: Any, default: float) -> float:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after")
    try:
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _to_result(model: str, response: Any, started: float) -> LLMResult:
    usage = getattr(response, "usage", None)
    return LLMResult(
        model=model,
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        latency_ms=(time.perf_counter() - started) * 1000,
        ok=True,
    )


def cache_read_tokens(response: Any) -> int:
    """PP-4 - surfaced separately so a 0% hit rate is visible as a regression."""
    usage = getattr(response, "usage", None)
    return getattr(usage, "cache_read_input_tokens", 0) or 0


def _extract_json(response: Any) -> dict[str, Any]:
    import json

    parsed = getattr(response, "parsed_output", None)
    if parsed is not None:
        return parsed if isinstance(parsed, dict) else dict(parsed)
    text = "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    )
    return json.loads(text)
