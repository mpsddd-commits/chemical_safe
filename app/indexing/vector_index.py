"""C25 VectorIndex (FR-11).

`scope` is a required argument on `search`, not an optional filter. In u1 there
is only ever the public corpus, so a default would be harmless today and a
silent data leak the moment u5 introduces uploaded documents (DD-19). Making it
required means the omission is a call-site error, not a runtime surprise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.types import Candidate, Scope
from app.db.models import ChunkEmbedding, ChunkRow

log = get_logger(__name__)


@dataclass(frozen=True)
class MetaFilter:
    """Metadata narrowing derived from the query (used from u2)."""

    cas_number: str | None = None
    un_number: str | None = None
    doc_types: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not (self.cas_number or self.un_number or self.doc_types)


def apply_scope(stmt, scope: Scope):
    """Public rows always; the caller's own rows in addition (FR-28 groundwork)."""
    if scope.owner_id is None:
        return stmt.where(ChunkRow.owner_id.is_(None))
    return stmt.where(
        (ChunkRow.owner_id.is_(None)) | (ChunkRow.owner_id == scope.owner_id)
    )


def apply_meta_filter(stmt, filters: MetaFilter):
    if filters.cas_number:
        stmt = stmt.where(ChunkRow.meta["cas_number"].astext == filters.cas_number)
    if filters.un_number:
        stmt = stmt.where(ChunkRow.meta["un_number"].astext == filters.un_number)
    if filters.doc_types:
        stmt = stmt.where(ChunkRow.meta["doc_type"].astext.in_(list(filters.doc_types)))
    return stmt


class VectorIndex:
    def __init__(self, session: Session) -> None:
        self._s = session

    def search(
        self,
        vector: list[float],
        top_k: int,
        filters: MetaFilter,
        scope: Scope,
        model_id: str,
    ) -> list[Candidate]:
        """Cosine distance ordering. Consumed by u2's retrieval pipeline."""
        distance = ChunkEmbedding.embedding.cosine_distance(vector)
        stmt = (
            select(ChunkRow.id, distance.label("distance"))
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == ChunkRow.id)
            .where(ChunkEmbedding.model_id == model_id)
        )
        stmt = apply_scope(stmt, scope)
        stmt = apply_meta_filter(stmt, filters)
        stmt = stmt.order_by(distance).limit(top_k)

        rows: list[Any] = self._s.execute(stmt).all()
        # Cosine distance in [0, 2]; convert to a similarity so fusion in u2 can
        # treat every route's score as "higher is better".
        return [
            Candidate(chunk_id=row[0], score=1.0 - float(row[1]), route="vector")
            for row in rows
        ]

    def count_for_model(self, model_id: str) -> int:
        from sqlalchemy import func

        return (
            self._s.scalar(
                select(func.count())
                .select_from(ChunkEmbedding)
                .where(ChunkEmbedding.model_id == model_id)
            )
            or 0
        )
