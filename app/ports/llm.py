"""C6 LLMPort.

Defined in u1, implemented in u2. Structured generation is a first-class method
rather than an afterthought because the citation contract depends on it: the
model returns {sentence, evidence_ids} objects, which is what makes grounding
verification deterministic (DD-8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class LLMResult:
    """Always returned alongside the payload so the tracing decorator has
    something to record (DD-16)."""

    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    ok: bool
    error: str | None = None


@runtime_checkable
class LLMPort(Protocol):
    def generate(self, prompt: str, system: str | None = None) -> tuple[str, LLMResult]:
        ...

    def generate_structured(
        self, prompt: str, schema: dict[str, Any], system: str | None = None
    ) -> tuple[dict[str, Any], LLMResult]:
        ...
