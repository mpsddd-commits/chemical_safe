"""C7 EmbeddingPort (NFR-21)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingPort(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def dimension(self) -> int:
        ...

    def model_id(self) -> str:
        """Used to decide whether a re-index is required (FR-13, BR-55)."""
        ...
