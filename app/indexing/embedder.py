"""C24 Embedder (FR-11, BR-61, BR-62).

Batching keeps peak memory bounded on a 4G worker (risk R-3); the cache exists
because this corpus repeats itself - standard MSDS phrasing and boilerplate
disclaimers recur across hundreds of documents, and re-encoding them is pure
waste (NFR-4, NFR-20).
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.types import Chunk
from app.ports.embedding import EmbeddingPort

log = get_logger(__name__)


class Embedder:
    def __init__(self, port: EmbeddingPort, settings: Settings | None = None) -> None:
        self._port = port
        self._settings = settings or get_settings()

    def model_id(self) -> str:
        return self._port.model_id()

    def dimension(self) -> int:
        return self._port.dimension()

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        if not chunks:
            return []
        texts = [c.text for c in chunks]
        batch = self._settings.embed_batch_size
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch):
            vectors.extend(self._port.embed(texts[start : start + batch]))
        if len(vectors) != len(chunks):
            raise RuntimeError(
                f"embedder returned {len(vectors)} vectors for {len(chunks)} chunks"
            )
        return vectors

    def embed_query(self, query: str) -> list[float]:
        """Used from u2. Present here so query and document embeddings can never
        drift onto different models."""
        return self._port.embed([query])[0]
