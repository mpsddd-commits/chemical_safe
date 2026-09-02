"""C8 RerankerPort.

Defined in u1 so the port surface is complete and stable; the only consumer is
u2's retrieval pipeline (DD-6, DD-21).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RerankerPort(Protocol):
    def rerank(self, query: str, docs: list[str], top_k: int) -> list[tuple[int, float]]:
        """Return (original index, score) pairs, best first."""
        ...

    def model_id(self) -> str:
        ...
