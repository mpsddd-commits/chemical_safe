"""DocumentRepo and ChunkRepo.

Both index writes happen inside the caller's transaction so the keyword index
and the vector index can never drift apart (DD-23).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.types import Chunk, DocType, Scope, StructureStatus, SubstanceRelation
from app.db.models import (
    ChunkEmbedding,
    ChunkRow,
    Document,
    DocumentSection,
    DocumentSubstance,
    ExtractedTextRow,
)


class DocumentRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, document_id: int) -> Document | None:
        return self._s.get(Document, document_id)

    def find_by_external(self, source_pk: int | None, external_id: str | None) -> Document | None:
        if external_id is None:
            return None
        return self._s.scalar(
            select(Document).where(
                Document.source_id == source_pk, Document.external_id == external_id
            )
        )

    def find_by_hash(self, content_hash: str) -> Document | None:
        return self._s.scalar(select(Document).where(Document.content_hash == content_hash))

    def upsert(
        self,
        *,
        source_pk: int | None,
        external_id: str | None,
        doc_type: DocType,
        source_url: str,
        title: str | None = None,
        published_at: datetime | None = None,
        revised_at: datetime | None = None,
        content_hash: str | None = None,
        original_path: str | None = None,
        original_media_type: str | None = None,
        structure_status: StructureStatus = StructureStatus.STRUCTURED,
        law_name: str | None = None,
        incident_occurred_at: datetime | None = None,
        owner_id: int | None = None,
    ) -> Document:
        """BR-32 - refuses to persist a document with no traceable origin."""
        if not source_url or not doc_type:
            raise ValueError("source_url and doc_type are required (BR-32)")

        doc = self.find_by_external(source_pk, external_id)
        if doc is None:
            doc = Document(source_id=source_pk, external_id=external_id, doc_type=doc_type.value,
                           source_url=source_url)
            self._s.add(doc)
        doc.doc_type = doc_type.value
        doc.source_url = source_url
        doc.title = title
        doc.published_at = published_at
        doc.revised_at = revised_at
        doc.content_hash = content_hash
        doc.original_path = original_path
        doc.original_media_type = original_media_type
        doc.structure_status = structure_status.value
        doc.law_name = law_name
        doc.incident_occurred_at = incident_occurred_at
        doc.owner_id = owner_id  # always None in u1 (DD-21)
        self._s.flush()
        return doc

    def set_extracted_text(self, document: Document, text: str, extractor: str) -> None:
        if document.extracted is not None:
            self._s.delete(document.extracted)
            self._s.flush()
        self._s.add(
            ExtractedTextRow(
                document_id=document.id, text=text, char_count=len(text), extractor=extractor
            )
        )
        self._s.flush()

    def get_extracted_text(self, document_id: int) -> str | None:
        row = self._s.scalar(
            select(ExtractedTextRow).where(ExtractedTextRow.document_id == document_id)
        )
        return row.text if row else None

    def replace_sections(self, document: Document, sections: list[dict]) -> list[DocumentSection]:
        """BR-24 - an ``unstructured`` document simply gets an empty list."""
        self._s.execute(
            delete(DocumentSection).where(DocumentSection.document_id == document.id)
        )
        rows = [
            DocumentSection(
                document_id=document.id,
                ordinal=s["ordinal"],
                section_code=s.get("section_code"),
                section_title=s.get("section_title"),
                start_offset=s["start_offset"],
                end_offset=s["end_offset"],
            )
            for s in sections
        ]
        self._s.add_all(rows)
        self._s.flush()
        return rows

    def link_substances(
        self, document: Document, links: list[tuple[int, SubstanceRelation]]
    ) -> None:
        """BR-37 - one relation per substance, not per document.

        It used to be per document, which was enough while the only linked
        documents were the substance API's own records: one record, one
        substance, subject. A document found by scanning its text carries both
        kinds at once - an MSDS for 황산 that lists 톨루엔 among its constituents
        is the subject of one and mentions the other - and collapsing that into
        a single relation makes the card claim the wrong thing.
        """
        self._s.execute(
            delete(DocumentSubstance).where(DocumentSubstance.document_id == document.id)
        )
        seen: set[int] = set()
        for sid, relation in links:
            if sid in seen:
                continue
            seen.add(sid)
            self._s.add(
                DocumentSubstance(
                    document_id=document.id, substance_id=sid, relation=relation.value
                )
            )
        self._s.flush()

    def substance_mentions(self, exclude_source_pk: int | None = None) -> list[str]:
        """BR-08 - the substance names the corpus already talks about.

        Two shapes, one purpose. An accident record carries the substances
        involved in a labelled section ("substances: 암모니아(100%)"), and an MSDS
        document is titled after the substance it documents
        ("황산 (SULFURIC ACID) - 남해화학"). Both say the same thing: this system
        holds documents about that substance, so the substance master had
        better contain it.

        `exclude_source_pk` keeps the substance source itself out of the answer.
        Ranking a listing by the names already collected from that same listing
        would only entrench whatever the first run happened to pick up.

        Titles are taken from MSDS documents only. A statute or an accident is
        titled after an event or a law, not after a chemical, and feeding those
        in is noise with a real chance of matching something by accident.
        """
        sections = self._s.execute(
            select(
                func.substring(
                    ExtractedTextRow.text,
                    DocumentSection.start_offset + 1,
                    DocumentSection.end_offset - DocumentSection.start_offset,
                )
            ).join(
                DocumentSection,
                DocumentSection.document_id == ExtractedTextRow.document_id,
            ).where(DocumentSection.section_code == "incident_substance")
        ).all()

        stmt = select(Document.title).where(
            Document.doc_type == DocType.MSDS.value, Document.title.isnot(None)
        )
        if exclude_source_pk is not None:
            stmt = stmt.where(Document.source_id != exclude_source_pk)
        titles = self._s.execute(stmt).all()

        return [str(row[0]) for row in [*sections, *titles] if row[0]]

    def delete(self, document_id: int) -> None:
        """BR-56 - cascades remove text, sections, chunks, embeddings and links.
        Removing the stored original file is the caller's responsibility inside
        the same transaction."""
        doc = self.get(document_id)
        if doc is not None:
            self._s.delete(doc)
            self._s.flush()

    def count(self) -> int:
        return self._s.scalar(select(func.count()).select_from(Document)) or 0

    def iter_all_ids(self) -> list[int]:
        return list(self._s.scalars(select(Document.id).order_by(Document.id)))


class ChunkRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def replace_for_document(
        self,
        document: Document,
        chunks: list[Chunk],
        section_rows: list[DocumentSection],
        owner_id: int | None = None,
    ) -> list[ChunkRow]:
        """BR-54 - delete then re-insert. Partial updates are never attempted, so
        re-processing the same document is idempotent."""
        self._s.execute(delete(ChunkRow).where(ChunkRow.document_id == document.id))
        by_ordinal = {row.ordinal: row.id for row in section_rows}
        rows: list[ChunkRow] = []
        for chunk in chunks:
            section_id = (
                by_ordinal.get(chunk.section_ordinal)
                if chunk.section_ordinal is not None
                else None
            )
            row = ChunkRow(
                document_id=document.id,
                section_id=section_id,
                ordinal=chunk.ordinal,
                text=chunk.text,
                token_count=chunk.token_count,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                owner_id=owner_id,  # always None in u1 (DD-21)
                meta=chunk.meta.to_dict(),
            )
            self._s.add(row)
            rows.append(row)
        self._s.flush()
        return rows

    def add_embeddings(
        self, rows: list[ChunkRow], vectors: list[list[float]], model_id: str, dim: int
    ) -> int:
        """BR-55 - vectors for a new model are added alongside existing ones, so a
        model swap never takes search offline."""
        if len(rows) != len(vectors):
            raise ValueError("chunk/vector count mismatch")
        for row, vector in zip(rows, vectors, strict=True):
            self._s.execute(
                delete(ChunkEmbedding).where(
                    ChunkEmbedding.chunk_id == row.id, ChunkEmbedding.model_id == model_id
                )
            )
            self._s.add(
                ChunkEmbedding(chunk_id=row.id, model_id=model_id, dim=dim, embedding=vector)
            )
        self._s.flush()
        return len(rows)

    def get_many(self, chunk_ids: list[int]) -> list[ChunkRow]:
        if not chunk_ids:
            return []
        return list(self._s.scalars(select(ChunkRow).where(ChunkRow.id.in_(chunk_ids))))

    def count(self) -> int:
        return self._s.scalar(select(func.count()).select_from(ChunkRow)) or 0

    def count_for_scope(self, scope: Scope) -> int:
        """``scope`` is required on every read path (DD-19). In u1 it always
        resolves to the public corpus."""
        stmt = select(func.count()).select_from(ChunkRow)
        if scope.owner_id is None:
            stmt = stmt.where(ChunkRow.owner_id.is_(None))
        else:
            stmt = stmt.where(
                (ChunkRow.owner_id.is_(None)) | (ChunkRow.owner_id == scope.owner_id)
            )
        return self._s.scalar(stmt) or 0

    def distinct_embedding_models(self) -> list[str]:
        return list(self._s.scalars(select(ChunkEmbedding.model_id).distinct()))
