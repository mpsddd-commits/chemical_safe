"""C13 - tracing decorators for the three model ports (DD-16, FR-41).

Instrumentation lives here rather than in the services so that a call cannot be
made without being recorded. Callers hold a port and never learn that tracing
exists.

Cost estimation uses a per-model rate table; local models are free (NFR-20), so
their cost is recorded as 0 rather than omitted - a missing number and a genuine
zero are different things.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger
from app.db.repositories.jobs import TraceRepo
from app.ports.llm import LLMResult

log = get_logger(__name__)

def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """USD for one call, or None when the model has no registered price.

    u1 kept a hard-coded table here and returned 0.0 for anything missing. That
    was harmless while nothing called an LLM and became a defect the moment
    something did: BR-96 requires unknown to read as unknown, because 0 makes
    the usage screen say "free". Rates now live in `config/llm_pricing.yaml`
    (CP-1) where they can be corrected without a release - the u1 table had
    opus-5 at $15/$75 against an actual $5/$25.
    """
    from app.rag.pricing import shared_pricing

    cost = shared_pricing().cost_for(
        model, input_tokens=input_tokens, output_tokens=output_tokens
    )
    return float(cost) if cost is not None else None


class _TracerBase:
    def __init__(self, trace_repo: TraceRepo | None = None) -> None:
        self._traces = trace_repo

    def _record(self, **fields: Any) -> None:
        log.info("model_call", extra=fields)
        if self._traces is not None:
            self._traces.record(**fields)


class TracedLLM(_TracerBase):
    """Wraps an LLMPort. Used from u2 onwards."""

    def __init__(self, inner: Any, trace_repo: TraceRepo | None = None) -> None:
        super().__init__(trace_repo)
        self._inner = inner

    def generate(self, prompt: str, system: str | None = None) -> tuple[str, LLMResult]:
        started = time.perf_counter()
        try:
            text, result = self._inner.generate(prompt, system)
        except Exception as exc:
            self._emit("generate", None, started, ok=False, error=str(exc))
            raise
        self._emit("generate", result, started, ok=True)
        return text, result

    def generate_structured(
        self, prompt: str, schema: dict[str, Any], system: str | None = None
    ) -> tuple[dict[str, Any], LLMResult]:
        started = time.perf_counter()
        try:
            payload, result = self._inner.generate_structured(prompt, schema, system)
        except Exception as exc:
            self._emit("generate_structured", None, started, ok=False, error=str(exc))
            raise
        self._emit("generate_structured", result, started, ok=True)
        return payload, result

    def _emit(
        self,
        operation: str,
        result: LLMResult | None,
        started: float,
        *,
        ok: bool,
        error: str | None = None,
    ) -> None:
        elapsed_ms = (time.perf_counter() - started) * 1000
        model = result.model if result else "unknown"
        in_tok = result.input_tokens if result else 0
        out_tok = result.output_tokens if result else 0
        cost = estimate_cost_usd(model, in_tok, out_tok)
        self._record(
            kind="llm",
            operation=operation,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=round(elapsed_ms, 2),
            # None, not 0, when the model is unpriced (BR-96).
            cost_usd=round(cost, 6) if cost is not None else None,
            ok=ok,
            error=error,
        )


class TracedEmbedding(_TracerBase):
    """Wraps an EmbeddingPort. This is the only traced port active in u1."""

    def __init__(self, inner: Any, trace_repo: TraceRepo | None = None) -> None:
        super().__init__(trace_repo)
        self._inner = inner

    def model_id(self) -> str:
        return self._inner.model_id()

    def dimension(self) -> int:
        return self._inner.dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        started = time.perf_counter()
        try:
            vectors = self._inner.embed(texts)
        except Exception as exc:
            self._record(
                kind="embedding",
                operation="embed",
                model=self._inner.model_id(),
                item_count=len(texts),
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                cost_usd=0.0,
                ok=False,
                error=str(exc),
            )
            raise
        self._record(
            kind="embedding",
            operation="embed",
            model=self._inner.model_id(),
            item_count=len(texts),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            cost_usd=0.0,
            ok=True,
        )
        return vectors


class TracedReranker(_TracerBase):
    """Wraps a RerankerPort. Idle in u1; used by u2."""

    def __init__(self, inner: Any, trace_repo: TraceRepo | None = None) -> None:
        super().__init__(trace_repo)
        self._inner = inner

    def model_id(self) -> str:
        return self._inner.model_id()

    def rerank(self, query: str, docs: list[str], top_k: int) -> list[tuple[int, float]]:
        started = time.perf_counter()
        try:
            ranked = self._inner.rerank(query, docs, top_k)
        except Exception as exc:
            self._record(
                kind="reranker",
                operation="rerank",
                model=self._inner.model_id(),
                item_count=len(docs),
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                cost_usd=0.0,
                ok=False,
                error=str(exc),
            )
            raise
        self._record(
            kind="reranker",
            operation="rerank",
            model=self._inner.model_id(),
            item_count=len(docs),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            cost_usd=0.0,
            ok=True,
        )
        return ranked
