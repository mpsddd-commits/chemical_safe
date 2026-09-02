"""N6 - the decorator that actually writes `llm_call` rows (FR-41, BR-95).

u1's `TracedLLM` records into the in-memory `TraceRepo`, which was the right
stand-in while nothing called an LLM. u2 promoted that store to a real table
(E18), and this is the decorator that fills it.

It wraps the port rather than living in the services, for the same reason u1 put
`TracedEmbedding` there (DD-16): a call cannot be made without being recorded.
Callers hold something that looks exactly like an `LLMPort` and never learn
tracing exists.

**Failed calls are recorded too** (BR-95). A usage view built only from successes
understates what was spent, and the failures are precisely what you want when
the numbers look wrong - a 429 storm is invisible in a success-only ledger.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import ConfigurationError
from app.core.logging import get_logger
from app.core.types import LlmPurpose
from app.db.repositories.traces import LlmCallRepo
from app.rag.pricing import PricingTable, shared_pricing

log = get_logger(__name__)


@dataclass
class CallContext:
    """Mutable because `query_id` only exists after the log row is opened.

    `prompt_name`/`prompt_version` are set by the assembler on each call, so
    they travel here rather than being fixed at construction (BR-95).
    """

    query_id: int | None = None
    prompt_name: str | None = None
    prompt_version: str | None = None
    extra: dict = field(default_factory=dict)


class TracedLlm:
    def __init__(
        self,
        inner: Any,
        repo: LlmCallRepo,
        purpose: LlmPurpose,
        context: CallContext,
        provider: str = "gemini",
        pricing: PricingTable | None = None,
    ) -> None:
        self._inner = inner
        self._repo = repo
        self._purpose = purpose
        self._context = context
        self._provider = provider
        self._pricing = pricing or shared_pricing()

    @property
    def model(self) -> str:
        return getattr(self._inner, "model", "unknown")

    def generate(self, prompt: str, system: str | None = None):
        return self._run("generate", lambda: self._inner.generate(prompt, system))

    def generate_structured(self, prompt: str, schema: dict, system: str | None = None):
        return self._run(
            "generate_structured",
            lambda: self._inner.generate_structured(prompt, schema, system),
        )

    def stream_structured(
        self, prompt: str, schema: dict, system: str | None = None, on_delta: Any = None
    ):
        streamer = getattr(self._inner, "stream_structured", None)
        if streamer is None:
            return self.generate_structured(prompt, schema, system)
        return self._run(
            "stream_structured", lambda: streamer(prompt, schema, system, on_delta)
        )

    # ---- internals ----

    def _run(self, operation: str, call):
        started = time.perf_counter()
        try:
            payload, result = call()
        except ConfigurationError:
            # BR-02 - no key configured. Not a call that happened, so not a call
            # to record; recording it would inflate the failure count with
            # something that never reached the provider.
            raise
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
            self._record(
                started, ok=False, error_kind=type(exc).__name__, result=None
            )
            raise
        self._record(started, ok=True, error_kind=None, result=result)
        return payload, result

    def _record(self, started: float, *, ok: bool, error_kind: str | None, result) -> None:
        latency_ms = int((time.perf_counter() - started) * 1000)
        model = getattr(result, "model", None) or self.model
        input_tokens = getattr(result, "input_tokens", None)
        output_tokens = getattr(result, "output_tokens", None)
        cached = self._context.extra.get("cache_read_tokens")

        cost = self._pricing.cost_for(
            model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cached,
        )
        try:
            self._repo.record(
                purpose=self._purpose,
                provider=self._provider,
                model=model,
                latency_ms=latency_ms,
                ok=ok,
                query_id=self._context.query_id,
                prompt_name=self._context.prompt_name,
                prompt_version=self._context.prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cached,
                # None, never 0, for an unpriced model (BR-96).
                cost_usd=cost,
                error_kind=error_kind,
            )
        except Exception as exc:  # noqa: BLE001
            # Observability must not be able to fail the query it observes.
            log.warning("llm_trace_write_failed", extra={"error": str(exc)})
