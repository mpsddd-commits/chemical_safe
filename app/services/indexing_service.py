"""S2 IndexingService - workflows W2, W3 and W4.

The transaction boundary is one document (DD-24, BR-53). A job over a thousand
documents is a thousand transactions, not one: a long-running transaction would
hold locks for hours and would throw away every success on the first failure.

Within that transaction the chunk rows and their vectors are written together
(DD-23), so the keyword index and the vector index cannot disagree about what
exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.embedding_local import DeterministicEmbeddingAdapter, shared_adapter
from app.adapters.tracing import TracedEmbedding
from app.core.config import Settings, get_settings
from app.core.errors import EmbeddingUnavailableError, MissingRequiredMetadataError
from app.core.logging import get_logger
from app.core.types import (
    ChunkMeta,
    DocType,
    PipelineStage,
    RawDocument,
    SubstanceRelation,
)
from app.db.models import Document
from app.db.repositories.catalog import SourceRepo, SubstanceRepo
from app.db.repositories.documents import ChunkRepo, DocumentRepo
from app.db.repositories.jobs import JobRepo, TraceRepo
from app.indexing.embedder import Embedder
from app.indexing.keyword_index import CAS_PATTERN
from app.indexing.reindexer import Reindexer
from app.ingestion import substance_selection
from app.processing.runner import PipelineRunner
from app.processing.tokens import count_tokens  # noqa: F401 - re-exported for tests

log = get_logger(__name__)

def _named_in_title(substance, title: str | None) -> bool:
    """Substring, not exact - a title is "황산 (SULFURIC ACID) - 남해화학".

    The opposite of BR-08 selection, where substring matching had to be ruled
    out: there a loose match steals a slot from the substance the user wants,
    here it only ever upgrades `mentioned` to the document type's own relation.
    """
    if not title:
        return False
    haystack = substance_selection.normalise(title)
    return any(
        substance_selection.normalise(name) in haystack
        for name in (substance.name_ko, substance.name_en)
        if name
    )


_RELATION_BY_DOC_TYPE = {
    DocType.MSDS: SubstanceRelation.SUBJECT,
    DocType.SUBSTANCE: SubstanceRelation.SUBJECT,
    DocType.INCIDENT: SubstanceRelation.MENTIONED,
    DocType.LAW: SubstanceRelation.REGULATED,
    DocType.USER_UPLOAD: SubstanceRelation.SUBJECT,
}


@dataclass
class IndexOutcome:
    document_id: int
    chunk_count: int
    structure_status: str
    embedded: bool


def build_embedder(settings: Settings, traces: TraceRepo | None = None) -> Embedder:
    """Falls back to the deterministic stand-in when the ML stack is absent.

    This keeps `docker compose up` usable before the model volume is warm and
    keeps tests network-free (NFR-28). The fallback is logged loudly because its
    vectors are not semantically meaningful.
    """
    try:
        # Shared per process: a per-document adapter reloaded the model for every
        # document (measured: 8 loads for 8 documents, worker at 3.999/4 GiB).
        port = shared_adapter(settings)
        port.dimension()
        import importlib.util

        if importlib.util.find_spec("sentence_transformers") is None:
            raise EmbeddingUnavailableError("sentence-transformers not installed")
    except EmbeddingUnavailableError as exc:
        log.warning(
            "embedding_fallback_deterministic",
            extra={"reason": str(exc), "impact": "vector search results are not meaningful"},
        )
        port = DeterministicEmbeddingAdapter(settings.embedding_dim)
    return Embedder(TracedEmbedding(port, traces), settings)


class IndexingService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._s = session
        self._settings = settings or get_settings()
        self._documents = DocumentRepo(session)
        self._chunks = ChunkRepo(session)
        self._sources = SourceRepo(session)
        self._substances = SubstanceRepo(session)
        self._jobs = JobRepo(session)
        self._traces = TraceRepo(session)
        self._runner = PipelineRunner(self._settings)
        self._embedder = build_embedder(self._settings, self._traces)
        self._reindexer = Reindexer(self._documents, self._chunks)

    # ---- W2 + W3 ----
    def process(
        self,
        raw: RawDocument,
        doc_type: DocType,
        *,
        source_pk: int | None,
        from_stage: PipelineStage | None = None,
        owner_id: int | None = None,
    ) -> IndexOutcome:
        ref = raw.ref
        if not ref.url:
            # BR-32 - refuse rather than index something untraceable.
            raise MissingRequiredMetadataError("source_url missing", detail=ref.ref_key)

        # BR-38 needs `meta.cas_number` populated or exact identifier matching
        # has nothing to match against - it read only `ref.extra`, which the
        # list adapter never fills, so the field was NULL on every chunk (the
        # third face of defect 40). The payload is authoritative; `extra` stays
        # as a fallback for sources that do carry it there.
        payload = raw.payload or {}
        base_meta = ChunkMeta(
            doc_type=doc_type.value,
            source_url=ref.url,
            published_at=ref.published_at.isoformat() if ref.published_at else None,
            cas_number=payload.get("cas_number") or ref.extra.get("cas_number"),
            un_number=payload.get("un_number") or ref.extra.get("un_number"),
            law_name=ref.extra.get("law_name"),
        )

        ctx = self._runner.run(raw, doc_type, base_meta, from_stage=from_stage)
        assert ctx.extracted is not None and ctx.structured is not None

        document = self._documents.upsert(
            source_pk=source_pk,
            external_id=ref.external_id,
            doc_type=doc_type,
            source_url=ref.url,
            title=ref.extra.get("title"),
            published_at=ref.published_at,
            revised_at=ref.revised_at,
            content_hash=ref.content_hash,
            original_path=ctx.stored_path,
            original_media_type=raw.media_type,
            structure_status=ctx.structured.structure_status,
            law_name=ref.extra.get("law_name"),
            owner_id=owner_id,
        )
        self._documents.set_extracted_text(
            document, ctx.extracted.text, ctx.extracted.extractor
        )
        section_rows = self._documents.replace_sections(
            document,
            [
                {
                    "ordinal": s.ordinal,
                    "section_code": s.section_code,
                    "section_title": s.section_title,
                    "start_offset": s.start_offset,
                    "end_offset": s.end_offset,
                }
                for s in ctx.structured.sections
            ],
        )

        # BR-97 - project the substance master from the record itself, inside
        # the indexing path. Defect 40: the write path existed and nobody called
        # it, which is what a detached backfill command invites.
        self._project_substance(raw)

        links = self._resolve_substances(raw, doc_type, ctx.extracted.text, document.title)
        if links:
            self._documents.link_substances(document, links)
            substance_ids = list(dict.fromkeys(sid for sid, _relation in links))
            for chunk in ctx.chunks:
                chunk.meta.substance_ids = substance_ids

        # BR-54 - full replace keeps re-processing idempotent.
        chunk_rows = self._chunks.replace_for_document(
            document, ctx.chunks, section_rows, owner_id=owner_id
        )

        embedded = False
        if chunk_rows:
            vectors = self._embedder.embed_chunks(ctx.chunks)
            # DD-23 - same transaction as the chunk rows above.
            self._chunks.add_embeddings(
                chunk_rows, vectors, self._embedder.model_id(), self._embedder.dimension()
            )
            embedded = True

        log.info(
            "document_indexed",
            extra={
                "document_id": document.id,
                "ref_key": ref.ref_key,
                "chunks": len(chunk_rows),
                "structure_status": ctx.structured.structure_status.value,
            },
        )
        return IndexOutcome(
            document_id=document.id,
            chunk_count=len(chunk_rows),
            structure_status=ctx.structured.structure_status.value,
            embedded=embedded,
        )

    # ---- W4 ----
    def reindex_document(self, document_id: int) -> IndexOutcome:
        document = self._documents.get(document_id)
        if document is None:
            raise LookupError(f"document {document_id} not found")
        if not document.original_path:
            raise MissingRequiredMetadataError(
                "no retained original; re-collect this document instead",
                detail=str(document_id),
            )
        raw = self._raw_from_original(document)
        return self.process(
            raw,
            DocType(document.doc_type),
            source_pk=document.source_id,
            from_stage=PipelineStage.EXTRACT,
            owner_id=document.owner_id,
        )

    def reindex_job(self, job_id: int, scope: str = "all") -> dict:
        from app.core.errors import classify
        from app.db.engine import session_scope
        from app.jobs.tracker import JobTracker

        # Progress is committed per item so the job screen is not blank for the
        # whole run (FR-6), and per-document work gets its own transaction so a
        # failure late in the job does not undo earlier successes (DD-24).
        tracker = JobTracker(self._jobs, commit=self._s.commit)
        tracker.start(job_id)
        document_ids = self._reindexer.documents_to_reindex(scope)
        tracker.add_items(job_id, [str(d) for d in document_ids])

        succeeded = failed = 0
        for document_id in document_ids:
            try:
                with session_scope() as doc_session:
                    outcome = IndexingService(doc_session, self._settings).reindex_document(
                        document_id
                    )
            except Exception as exc:  # noqa: BLE001 - one document never stops the run
                tracker.mark_failed(
                    job_id, str(document_id), classify(exc), str(exc),
                    last_stage=PipelineStage.EXTRACT,
                )
                failed += 1
            else:
                tracker.mark_succeeded(job_id, str(document_id), outcome.document_id)
                succeeded += 1
        status = tracker.finalize(job_id)
        return {"succeeded": succeeded, "failed": failed, "status": status.value}

    def needs_reindex(self) -> bool:
        return self._reindexer.needs_reindex(self._embedder.model_id())

    # ---- helpers ----
    def _raw_from_original(self, document) -> RawDocument:
        import json
        from pathlib import Path

        from app.core.types import SourceRef

        path = Path(document.original_path)
        ref = SourceRef(
            source_id=document.source.source_id if document.source else "reindex",
            external_id=document.external_id or str(document.id),
            url=document.source_url,
            published_at=document.published_at,
            revised_at=document.revised_at,
            content_hash=document.content_hash,
            extra={"title": document.title, "law_name": document.law_name},
        )
        # The recorded media type wins over the file extension: it is what the
        # source actually returned. Guessing from the suffix made re-indexing
        # fail permanently on non-PDF originals (found in Build & Test).
        media_type = document.original_media_type or "application/octet-stream"
        if media_type == "application/json" or path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            return RawDocument(
                ref=ref, payload=payload, media_type="application/json", stored_path=str(path)
            )
        return RawDocument(
            ref=ref, content=path.read_bytes(), media_type=media_type, stored_path=str(path)
        )

    def _project_substance(self, raw) -> None:
        """BR-97~99. Silent when the payload is not a substance record."""
        from app.substances.projection import project

        project(self._substances, raw.payload)

    def _resolve_substances(
        self, raw, doc_type: DocType, text: str, title: str | None
    ) -> list[tuple[int, SubstanceRelation]]:
        """Link a document to substances it is about or mentions (BR-37).

        Reads the **payload**, not `ref.extra`. The list adapter files the record
        under `extra["row"]` while this looked for a top-level
        `extra["cas_number"]`, so it matched nothing for the whole of u1 and u2 -
        the read half of defect 40. `payload` is the same place whether the
        document was just fetched or rebuilt from its retained original (BR-44).

        A payload field is the only thing an API record needs. A **file** has no
        such field, and until now that meant every MSDS PDF linked to nothing:
        `document_substance` held exactly one row per substance API record and
        not one row for the eight PDFs - so a card for 황산 could not reach the
        two 황산 MSDS sitting in the corpus, which is the half of defect 44 that
        collecting the right substances does not fix on its own. The text
        carries the identifier ("7664-93-9" appears in section 3), so the text
        is what gets scanned.

        Only CAS numbers already in the master produce a link. That is the
        filter: `CAS_PATTERN` is deliberately loose and the master is what
        decides whether a match means anything.
        """
        payload = raw.payload or {}
        cas = payload.get("cas_number") or raw.ref.extra.get("cas_number")
        if cas:
            substance = self._substances.get_by_cas(str(cas))
            return [(substance.id, _RELATION_BY_DOC_TYPE[doc_type])] if substance else []

        links: list[tuple[int, SubstanceRelation]] = []
        seen: set[str] = set()
        for match in CAS_PATTERN.finditer(text or ""):
            value = match.group(0)
            if value in seen:
                continue
            seen.add(value)
            substance = self._substances.get_by_cas(value)
            if substance is None:
                continue
            # The title says what the document is *about*. An MSDS lists every
            # constituent, so without that signal a mixture datasheet would
            # claim to be the datasheet for each of its fourteen ingredients.
            relation = (
                _RELATION_BY_DOC_TYPE[doc_type]
                if _named_in_title(substance, title)
                else SubstanceRelation.MENTIONED
            )
            links.append((substance.id, relation))
        return links

    def retype_documents(self, *, apply: bool) -> dict:
        """Reconcile `document.doc_type` with `config/sources.yaml` (BR-32).

        The spec is the authority. Ingest already writes the declared type on
        every document it touches, so **new documents are always correct**; what
        drifts is rows collected before a spec changed. This makes that a
        command rather than a one-off SQL edit, because a spec can change again -
        `doc_type` was split into `substance` and `msds` on 2026-08-30 and the
        next such change should not need its own migration.

        Order matters and is enforced here: the row is updated **first**, then
        re-indexed. `reindex_document` reads `document.doc_type` from the row, so
        re-indexing before the update silently does nothing at all.

        Idempotent - a run with nothing to do reports zero and touches nothing.
        """
        from app.adapters.sources import load_source_specs

        declared = {
            str(spec["source_id"]): str(spec["doc_type"]) for spec in load_source_specs()
        }
        drifted: list[tuple[int, str, str]] = []
        for source_id, want in declared.items():
            source = self._sources.get(source_id)
            if source is None:
                continue
            rows = self._s.execute(
                select(Document.id, Document.doc_type).where(
                    Document.source_id == source.id, Document.doc_type != want
                )
            ).all()
            drifted.extend((doc_id, have, want) for doc_id, have in rows)

        if not apply:
            return {
                "checked": len(declared),
                "drifted": len(drifted),
                "documents": [
                    {"document_id": d, "from": h, "to": w} for d, h, w in drifted[:50]
                ],
                "applied": False,
            }

        reindexed = 0
        failed = 0
        for document_id, _have, want in drifted:
            document = self._documents.get(document_id)
            if document is None:
                continue
            document.doc_type = want
            self._s.flush()
            self._s.commit()
            try:
                # Chunk metadata carries `doc_type` too, and retrieval reads it
                # from there - the row alone is not enough.
                self.reindex_document(document_id)
            except Exception as exc:  # noqa: BLE001 - one document must not stop the run
                failed += 1
                log.warning(
                    "retype_reindex_failed",
                    extra={"document_id": document_id, "error": str(exc)},
                )
                continue
            reindexed += 1
        log.info(
            "retype_done",
            extra={"drifted": len(drifted), "reindexed": reindexed, "failed": failed},
        )
        return {
            "checked": len(declared),
            "drifted": len(drifted),
            "reindexed": reindexed,
            "failed": failed,
            "applied": True,
        }

    def stats(self) -> dict:
        return {
            "documents": self._documents.count(),
            "chunks": self._chunks.count(),
            "substances": self._substances.count(),
            "embedding_model": self._embedder.model_id(),
            "needs_reindex": self.needs_reindex(),
        }


def utcnow() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)
