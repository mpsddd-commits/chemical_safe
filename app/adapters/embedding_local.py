"""C11 - local embedding adapter (NFR-20: no per-call cost).

The heavy ML import is deferred to first use so that unit tests, the CLI and the
web process never pay for it and never need the model files (NFR-28).
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import EmbeddingUnavailableError
from app.core.logging import get_logger

log = get_logger(__name__)


class LocalEmbeddingAdapter:
    """Wraps a sentence-transformers model held in the `models` volume (ID-6).

    Batching and the identical-text cache implement BR-61 and BR-62; repeated
    boilerplate (disclaimer paragraphs, standard MSDS phrasing) is common enough
    in this corpus that the cache is not a micro-optimisation.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model: Any | None = None
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_limit = max(0, self._settings.embedding_cache_size)

    # ---- EmbeddingPort ----
    def model_id(self) -> str:
        return self._settings.embedding_model_id

    def dimension(self) -> int:
        return self._settings.embedding_dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        results: list[list[float] | None] = [None] * len(texts)
        pending: list[tuple[int, str]] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                results[i] = cached
            else:
                pending.append((i, text))

        batch_size = self._settings.embed_batch_size
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            vectors = self._encode([t for _, t in batch])
            for (index, text), vector in zip(batch, vectors, strict=True):
                results[index] = vector
                self._remember(self._cache_key(text), vector)

        missing = [i for i, v in enumerate(results) if v is None]
        if missing:
            raise EmbeddingUnavailableError(f"embedding missing for {len(missing)} texts")
        return [v for v in results if v is not None]

    # ---- internals ----
    @staticmethod
    def _cache_key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _remember(self, key: str, vector: list[float]) -> None:
        """Least-recently-used eviction (BR-61, BR-62).

        A 1024-dimension vector held as a Python list costs far more than its
        8KB of data. Across a full substance run that is tens of thousands of
        entries, so the cache is capped rather than allowed to become the
        largest object in the worker.
        """
        if self._cache_limit == 0:
            return
        self._cache[key] = vector
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_limit:
            self._cache.popitem(last=False)

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - exercised in Build & Test
                raise EmbeddingUnavailableError(
                    "sentence-transformers is not installed. "
                    "Install the 'ml' extra, or run in the worker container.",
                    detail=str(exc),
                ) from exc
            log.info(
                "embedding_model_loading",
                extra={
                    "model_id": self.model_id(),
                    "cache_dir": str(self._settings.model_cache_dir),
                },
            )
            try:
                self._model = SentenceTransformer(
                    self.model_id(), cache_folder=str(self._settings.model_cache_dir)
                )
                ceiling = self._settings.embed_max_seq_length
                if ceiling and getattr(self._model, "max_seq_length", 0) > ceiling:
                    self._model.max_seq_length = ceiling
            except Exception as exc:  # noqa: BLE001 - network/disk failure is transient
                raise EmbeddingUnavailableError(
                    f"could not load embedding model {self.model_id()}", detail=str(exc)
                ) from exc
            return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        try:
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingUnavailableError("embedding inference failed", detail=str(exc)) from exc
        out = [list(map(float, v)) for v in vectors]
        expected = self.dimension()
        for vector in out:
            if len(vector) != expected:
                raise EmbeddingUnavailableError(
                    f"model returned dim {len(vector)}, EMBEDDING_DIM is {expected}. "
                    "Fix the setting and re-index (BR-55)."
                )
        return out


_SHARED: dict[tuple[str, str, int], LocalEmbeddingAdapter] = {}
_SHARED_LOCK = threading.Lock()


def shared_adapter(settings: Settings | None = None) -> LocalEmbeddingAdapter:
    """One model per process, not one per document.

    `IndexingService` is constructed per document so that each document gets its
    own transaction (DD-24), and it used to build a fresh adapter with it - so
    BGE-M3 was loaded from disk again for every single document. Measured on the
    MSDS run: 8 documents, 8 model loads, and the worker sitting at 3.999 GiB of
    its 4 GiB limit. It also meant the identical-text cache was thrown away
    before it could ever match anything across documents, which is precisely
    what BR-61/62 wanted it for.

    Keyed by the settings that decide *which* model is loaded, so a model change
    still produces a different instance.
    """
    settings = settings or get_settings()
    key = (
        settings.embedding_model_id,
        str(settings.model_cache_dir),
        settings.embedding_dim,
    )
    adapter = _SHARED.get(key)
    if adapter is not None:
        return adapter
    with _SHARED_LOCK:
        adapter = _SHARED.get(key)
        if adapter is None:
            adapter = LocalEmbeddingAdapter(settings)
            _SHARED[key] = adapter
        return adapter


class DeterministicEmbeddingAdapter:
    """Offline stand-in used by tests and by a first run with no model files.

    It is a hash projection, not a semantic model: similarity is meaningless.
    Its only jobs are to keep the pipeline runnable end to end without network
    access (NFR-28) and to make dimension mismatches surface early.
    """

    def __init__(self, dim: int | None = None) -> None:
        self._dim = dim or get_settings().embedding_dim

    def model_id(self) -> str:
        return f"deterministic-hash-{self._dim}"

    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            raw = (digest * ((self._dim // len(digest)) + 1))[: self._dim]
            values = [(b - 128) / 128.0 for b in raw]
            norm = sum(v * v for v in values) ** 0.5 or 1.0
            vectors.append([v / norm for v in values])
        return vectors
