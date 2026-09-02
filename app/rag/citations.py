"""C41 - evidence resolution and citation display (W9, BR-89~92a).

Two directions, and they read from different places on purpose.

**Before an answer**, `resolve_evidence` builds `Evidence` from live chunks:
the snippet is `extracted_text.text[start:end]`, which BR-30 guarantees to equal
the chunk body (0 violations across 1,598 chunks, measured).

**After an answer**, display reads `citation_snapshot` and never joins `chunk`
(BR-92a). Re-indexing replaces chunk rows and reuses their ids, so resolving a
past citation through `chunk_id` could show a *different document's* text under
the original citation. The snapshot is what the answer actually relied on.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import DocType
from app.db.models import (
    AnswerCitationRow,
    AnswerSentenceRow,
    ChunkRow,
    CitationSnapshotRow,
    Document,
    DocumentSection,
)
from app.db.repositories.queries import CitationDraft
from app.rag.types import Evidence, RetrievalCandidate

NO_SECTION_LABEL = "섹션 정보 없음"


def resolve_evidence(
    session: Session, candidates: list[RetrievalCandidate]
) -> list[Evidence]:
    """Turn ranked chunk ids into the text the model will see."""
    if not candidates:
        return []
    chunk_ids = [c.chunk_id for c in candidates]
    rows = session.execute(
        select(
            ChunkRow.id,
            ChunkRow.document_id,
            ChunkRow.text,
            ChunkRow.start_offset,
            ChunkRow.end_offset,
            ChunkRow.meta,
            Document.source_url,
            Document.title,
            DocumentSection.section_code,
            DocumentSection.section_title,
        )
        .join(Document, Document.id == ChunkRow.document_id)
        .outerjoin(DocumentSection, DocumentSection.id == ChunkRow.section_id)
        .where(ChunkRow.id.in_(chunk_ids))
    ).all()

    by_id = {row[0]: row for row in rows}
    evidence: list[Evidence] = []
    for candidate in candidates:
        row = by_id.get(candidate.chunk_id)
        if row is None:
            # The chunk vanished between retrieval and resolution - a re-index
            # landed mid-query. Dropping it is right: we cannot cite what is not
            # there, and inventing a placeholder would be worse.
            continue
        (
            chunk_id,
            document_id,
            text,
            start_offset,
            end_offset,
            meta,
            source_url,
            title,
            section_code,
            section_title,
        ) = row
        meta = meta or {}
        try:
            doc_type = DocType(meta.get("doc_type"))
        except ValueError:
            doc_type = candidate.doc_type
        evidence.append(
            Evidence(
                chunk_id=chunk_id,
                document_id=document_id,
                source_url=source_url,
                document_title=title,
                section_code=section_code,
                section_title=section_title,
                text=text,
                start_offset=start_offset,
                end_offset=end_offset,
                score=candidate.score,
                relevance=candidate.relevance,
                exact_identifier=candidate.exact_identifier,
                doc_type=doc_type,
                suspected_injection=bool(meta.get("suspected_injection")),
            )
        )
    return evidence


def to_citation_draft(evidence: Evidence, rank: int) -> CitationDraft:
    """BR-92 - the snapshot is built from the evidence we actually used."""
    return CitationDraft(
        chunk_id=evidence.chunk_id,
        rank=rank,
        document_id=evidence.document_id,
        source_url=evidence.source_url,
        document_title=evidence.document_title,
        section_code=evidence.section_code,
        section_title=evidence.section_title,
        snippet=evidence.text,
        start_offset=evidence.start_offset,
        end_offset=evidence.end_offset,
    )


def display_label(section_code: str | None, section_title: str | None) -> str:
    """BR-90 - say "no section" rather than leaving it blank.

    A blank reads as "there is a label and it failed to load". Absent section
    labels are normal here: BR-20a demotions and BR-31a merged records genuinely
    have none, and inventing one would misstate where the text came from.
    """
    if section_code and section_title:
        return f"{section_code} {section_title}"
    if section_code:
        return section_code
    if section_title:
        return section_title
    return NO_SECTION_LABEL


def citations_for_answer(session: Session, query_id: int) -> list[dict]:
    """BR-92a - snapshot only. `chunk` is deliberately not joined."""
    rows = session.execute(
        select(
            AnswerSentenceRow.ordinal,
            AnswerCitationRow.id,
            AnswerCitationRow.rank,
            AnswerCitationRow.chunk_id,
            CitationSnapshotRow,
        )
        .join(AnswerCitationRow, AnswerCitationRow.sentence_id == AnswerSentenceRow.id)
        .join(
            CitationSnapshotRow,
            CitationSnapshotRow.citation_id == AnswerCitationRow.id,
        )
        .where(AnswerSentenceRow.query_id == query_id)
        .order_by(AnswerSentenceRow.ordinal, AnswerCitationRow.rank)
    ).all()

    return [
        {
            "sentence_ordinal": ordinal,
            "citation_id": citation_id,
            "rank": rank,
            # None means the chunk has since been re-indexed. Not an error, and
            # not a reason to hide the citation - the snapshot is complete.
            "chunk_id": chunk_id,
            "document_id": snap.document_id,
            "title": snap.document_title,
            "label": display_label(snap.section_code, snap.section_title),
            "snippet": snap.snippet,
            "source_url": snap.source_url,
            "stale": chunk_id is None,
        }
        for ordinal, citation_id, rank, chunk_id, snap in rows
    ]
