"""C31 / C32 - the two retrieval routes, plus the query-embedding cache (PP-3).

u1 already owns the index queries (`KeywordIndex`, `VectorIndex`). This module
adapts them to u2's needs rather than reimplementing them: it caches the query
vector, resolves chunk metadata for fusion, and - importantly - lets either
route fail without taking the search down (BR-72).

Deviation from the code-generation plan: `keyword.py` and `vector.py` were
planned as separate modules. They would have been two thin wrappers around
existing classes, so they are one file.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.types import Candidate, DocType, Scope
from app.db.models import ChunkRow, Substance, SubstanceSynonym
from app.indexing.keyword_index import KeywordIndex
from app.indexing.vector_index import MetaFilter, VectorIndex
from app.rag.types import QueryIntent

log = get_logger(__name__)


class QueryEmbeddingCache:
    """PP-3 - a small LRU in front of the embedding model.

    Keyed on the *normalised* query (BR-63). Using the raw text would miss on
    trivial spacing differences, and using a different normalisation than the
    index would be worse than no cache: the two would disagree about what
    "the same query" means.
    """

    def __init__(self, maxsize: int) -> None:
        self._maxsize = maxsize
        self._entries: OrderedDict[str, list[float]] = OrderedDict()

    def get_or_compute(self, key: str, compute) -> list[float]:
        if key in self._entries:
            self._entries.move_to_end(key)
            return self._entries[key]
        vector = compute()
        self._entries[key] = vector
        if len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)
        return vector

    def __len__(self) -> int:
        return len(self._entries)


@dataclass
class RouteResult:
    candidates: list[Candidate]
    failed: bool = False


class Retrievers:
    def __init__(
        self,
        session: Session,
        embedder,
        settings: Settings | None = None,
        cache: QueryEmbeddingCache | None = None,
    ) -> None:
        self._s = session
        self._embedder = embedder
        self._settings = settings or get_settings()
        self._cache = cache or QueryEmbeddingCache(self._settings.query_embed_cache_size)
        self._keyword = KeywordIndex(session)
        self._vector = VectorIndex(session)

    @staticmethod
    def meta_filter(intent: QueryIntent) -> MetaFilter:
        """BR-66 - identifiers narrow; a document-type *hint* never does.

        CAS and UN numbers are exact facts the user typed, so filtering on them
        is safe. A guessed document type is not a fact, and filtering on it
        removes the right answer without telling anyone.
        """
        return MetaFilter(
            cas_number=intent.cas_numbers[0] if intent.cas_numbers else None,
            un_number=intent.un_numbers[0] if intent.un_numbers else None,
        )

    def _isolated(self, name: str, run) -> RouteResult:
        """Run one route so its failure cannot take the other one down (BR-72).

        The savepoint is the whole point. Both routes share a Session, so a
        failed statement leaves PostgreSQL in `InFailedSqlTransaction` and every
        later statement on that connection is rejected - the second route then
        fails with a message about the first one's aborted transaction rather
        than anything about itself.

        Measured, not theorised: on the first real query the keyword route hit a
        `to_tsvector` type error, and the vector route reported "current
        transaction is aborted". "One route may fail" was unreachable in
        practice even though the try/except read correctly.
        """
        savepoint = self._s.begin_nested()
        try:
            result = RouteResult(run())
            savepoint.commit()
            return result
        except Exception as exc:  # noqa: BLE001 - BR-72: one route may fail
            savepoint.rollback()
            log.warning(f"{name}_route_failed", extra={"error": str(exc)})
            return RouteResult([], failed=True)

    def keyword(self, query: str, intent: QueryIntent, scope: Scope) -> RouteResult:
        return self._isolated(
            "keyword",
            lambda: self._keyword.search(
                query,
                top_k=self._settings.keyword_top_k,
                filters=self.meta_filter(intent),
                scope=scope,
                resolved_cas=self._cas_for_names(intent.substance_names),
            ),
        )

    def _cas_for_names(self, names: list[str]) -> tuple[str, ...]:
        """BR-65a - the consumer `substance_names` never had.

        BR-65 resolved a query's substance names to canonical terms and then
        nothing read them: grep found only the definition and serialisation
        sites, and u4 measured the cost as name queries 0/5 against CAS queries
        3/3 on the same records. This turns the resolved name into the one form
        the index can match exactly - the substance's CAS number, stamped into
        every chunk's meta at indexing time.

        Runs inside the keyword route's savepoint (BR-72), so a failure here
        degrades to plain text search rather than taking retrieval down.
        """
        if not names:
            return ()
        rows = self._s.execute(
            select(Substance.cas_number)
            .join(SubstanceSynonym, SubstanceSynonym.substance_id == Substance.id)
            .where(
                SubstanceSynonym.term.in_(names),
                Substance.cas_number.is_not(None),
            )
            .distinct()
            .limit(3)
        ).all()
        return tuple(row[0] for row in rows)

    def vector(self, normalised_query: str, intent: QueryIntent, scope: Scope) -> RouteResult:
        def run():
            vector = self._cache.get_or_compute(
                normalised_query, lambda: self._embedder.embed([normalised_query])[0]
            )
            return self._vector.search(
                vector,
                top_k=self._settings.vector_top_k,
                filters=self.meta_filter(intent),
                scope=scope,
                model_id=self._embedder.model_id(),
            )

        return self._isolated("vector", run)

    def chunk_metadata(
        self, chunk_ids: list[int]
    ) -> tuple[dict[int, DocType], dict[int, int]]:
        """doc_type and document_id per chunk - fusion needs both (BR-69)."""
        if not chunk_ids:
            return {}, {}
        rows = self._s.execute(
            select(ChunkRow.id, ChunkRow.document_id, ChunkRow.meta).where(
                ChunkRow.id.in_(chunk_ids)
            )
        ).all()
        doc_types: dict[int, DocType] = {}
        document_ids: dict[int, int] = {}
        for chunk_id, document_id, meta in rows:
            document_ids[chunk_id] = document_id
            raw = (meta or {}).get("doc_type")
            try:
                doc_types[chunk_id] = DocType(raw)
            except ValueError:
                # An unrecognised doc_type must not drop the candidate; it only
                # makes it ineligible for the spread rule.
                log.warning("unknown_doc_type", extra={"chunk_id": chunk_id, "value": raw})
        return doc_types, document_ids
