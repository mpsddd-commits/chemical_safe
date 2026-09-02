"""C27 Reindexer (FR-13, BR-54, BR-55).

Re-processing is delete-then-insert, never a partial update. That is what makes
running the same document twice produce the same result, which matters because
resumed jobs re-run documents that may have been half-written.

A model change does not delete anything: new vectors are written under the new
`model_id` alongside the old ones, and the active model is switched only once
the whole corpus has been re-embedded. Search keeps working throughout.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.db.repositories.documents import ChunkRepo, DocumentRepo

log = get_logger(__name__)


class Reindexer:
    def __init__(self, document_repo: DocumentRepo, chunk_repo: ChunkRepo) -> None:
        self._documents = document_repo
        self._chunks = chunk_repo

    def needs_reindex(self, current_model_id: str) -> bool:
        """True when any indexed chunk lacks a vector for the active model."""
        models = set(self._chunks.distinct_embedding_models())
        if not models:
            return self._chunks.count() > 0
        return current_model_id not in models

    def stale_models(self, current_model_id: str) -> list[str]:
        return [m for m in self._chunks.distinct_embedding_models() if m != current_model_id]

    def documents_to_reindex(self, scope: str = "all") -> list[int]:
        if scope not in {"all"}:
            raise ValueError(f"unsupported reindex scope: {scope!r}")
        return self._documents.iter_all_ids()
