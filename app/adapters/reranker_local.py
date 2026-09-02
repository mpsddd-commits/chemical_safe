"""C12 - cross-encoder reranker.

Implemented against the port in u1 so the interface is exercised, but nothing in
u1 calls it: reranking belongs to u2's retrieval pipeline (DD-5, DD-21).

Note for u2: loading a cross-encoder inside the `app` process may exceed its 2G
memory limit. `deployment-architecture.md` section 9 flags this for re-measurement.
"""

from __future__ import annotations

import threading
from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import EmbeddingUnavailableError
from app.core.logging import get_logger

log = get_logger(__name__)

DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"


class LocalRerankerAdapter:
    def __init__(self, settings: Settings | None = None, model_name: str | None = None) -> None:
        self._settings = settings or get_settings()
        self._model_name = model_name or DEFAULT_RERANKER_MODEL
        self._model: Any | None = None
        self._lock = threading.Lock()

    def model_id(self) -> str:
        return self._model_name

    def rerank(self, query: str, docs: list[str], top_k: int) -> list[tuple[int, float]]:
        if not docs:
            return []
        model = self._load()
        pairs = [(query, doc) for doc in docs]
        try:
            scores = model.predict(pairs, show_progress_bar=False)
        except Exception as exc:  # noqa: BLE001
            raise EmbeddingUnavailableError("rerank inference failed", detail=str(exc)) from exc
        ranked = sorted(enumerate(float(s) for s in scores), key=lambda p: p[1], reverse=True)
        return ranked[:top_k]

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise EmbeddingUnavailableError(
                    "sentence-transformers is not installed; reranking is unavailable",
                    detail=str(exc),
                ) from exc
            self._model = CrossEncoder(
                self._model_name, cache_folder=str(self._settings.model_cache_dir)
            )
            return self._model


class IdentityReranker:
    """No-op reranker. Keeps the pipeline assembleable when reranking is turned
    off by configuration (R-4 mitigation)."""

    def model_id(self) -> str:
        return "identity"

    def rerank(self, query: str, docs: list[str], top_k: int) -> list[tuple[int, float]]:
        return [(i, 1.0 - i * 1e-6) for i in range(min(len(docs), top_k))]
