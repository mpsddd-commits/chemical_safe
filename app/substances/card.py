"""C50 SubstanceCardBuilder - BR-102~108.

Three rules do the work, and each says the same thing from a different angle:
**do not let the card look more complete than it is.**

  * **Seven items, always, in order** (BR-102). Measured, most of the 40
    substances have no MSDS and six of seven items come back empty. Dropping the
    empty ones makes the card look finished, and the reader cannot tell "this
    substance has no protective-equipment data" from "this screen does not show
    protective equipment".
  * **Every source, not the best one** (BR-103). When two MSDS prescribe
    different equipment, the disagreement is the information.
  * **The gap count travels with the card** (BR-106), like u2's
    `unpriced_calls` (BR-96) and `removed` (BR-88).

And one about freshness: **no `citation_snapshot`** (BR-107). Snapshots freeze
what an answer cited (BR-92); a card is a current-state lookup, and freezing it
would keep showing stale safety information after the source was revised.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import CardItemKey, DocType, ExposureRoute, SubstanceRelation, ValueOrigin
from app.db.models import (
    ChunkRow,
    Document,
    DocumentSection,
    DocumentSubstance,
    ExtractedTextRow,
)
from app.substances.types import CardItem, ItemValue, SubstanceCard, SubstanceRef

# Which MSDS section backs which card item (FR-24).
_MSDS_SECTION_FOR: dict[CardItemKey, tuple[str, ...]] = {
    CardItemKey.GHS: ("msds_02",),
    CardItemKey.HP_CODES: ("msds_02",),
    CardItemKey.PHYSICAL: ("msds_09",),
    CardItemKey.PPE: ("msds_08",),
    CardItemKey.FIRST_AID: ("msds_04",),
    CardItemKey.STORAGE: ("msds_07",),
    CardItemKey.REGULATIONS: ("msds_15",),
}

# The substance API's exposure-route sections. The only broad data this unit
# has - 40/40 records carry inhale, skin and eye; 39/40 carry oral.
_ROUTE_SECTION: dict[str, ExposureRoute] = {
    "substance_inhale": ExposureRoute.INHALE,
    "substance_skin": ExposureRoute.SKIN,
    "substance_eye": ExposureRoute.EYE,
    "substance_oral": ExposureRoute.ORAL,
}


class SubstanceCardBuilder:
    def __init__(self, session: Session) -> None:
        self._s = session

    def build(self, ref: SubstanceRef) -> SubstanceCard:
        rows = self._sourced_chunks(ref.substance_id)
        items = [
            CardItem(key=key, values=self._values_for(key, rows))
            for key in CardItemKey  # declaration order is the display order
        ]
        return SubstanceCard(
            substance=ref, items=items, has_msds=self._has_msds(rows)
        )

    # ---- internals ----

    def _sourced_chunks(self, substance_id: int) -> list:
        """Every chunk of every document linked to this substance (BR-37).

        Public corpus only (`owner_id IS NULL`) - u5 widens this.

        A document BR-31a folded into one section-less chunk is read from its
        sections instead (see `_folded_section_rows`).
        """
        rows = self._chunk_rows(substance_id)
        candidates = _folded_candidates(rows)
        if not candidates:
            return rows
        return _unfold(rows, self._folded_section_rows(substance_id, candidates))

    def _chunk_rows(self, substance_id: int) -> list:
        return self._s.execute(
            select(
                ChunkRow.text,
                Document.id,
                Document.title,
                Document.source_url,
                Document.doc_type,
                DocumentSection.section_code,
                DocumentSection.section_title,
                DocumentSubstance.relation,
                ChunkRow.section_id,
            )
            .join(Document, Document.id == ChunkRow.document_id)
            .join(DocumentSubstance, DocumentSubstance.document_id == Document.id)
            .outerjoin(DocumentSection, DocumentSection.id == ChunkRow.section_id)
            .where(
                DocumentSubstance.substance_id == substance_id,
                ChunkRow.owner_id.is_(None),
            )
            .order_by(Document.id, ChunkRow.ordinal)
        ).all()

    def _folded_section_rows(self, substance_id: int, document_ids: set[int]) -> list:
        """Card rows cut from `extracted_text` along `document_section` (C3).

        BR-31a folds a document whose sections are too short to cite into one
        chunk with no section, and BR-104 finds card items by section code, so
        the whole document fell off its card (4-tert-뷰틸벤조산, document 69).

        The fix is on the reading side on purpose. Narrowing BR-31a or tagging
        the folded chunk changes chunking, which means a re-index, which changes
        the corpus and invalidates the 615 evaluation baseline - for 1 card in
        49. And nothing was lost: the section boundaries are still in
        `document_section`, and the text they index is still in
        `extracted_text`. Only the chunk was folded.

        The offsets are safe to apply to the stored text. NormalizeStage runs
        before StructureStage, the sections are found on the normalised text,
        and that same text is what `set_extracted_text` stores (FQ-5=A, BR-30);
        the two-column retry replaces text and sections together.

        Same scope as the chunk query: the substance link and the public corpus.
        """
        found = self._s.execute(
            select(
                ExtractedTextRow.text.label("full_text"),
                DocumentSection.start_offset,
                DocumentSection.end_offset,
                Document.id,
                Document.title,
                Document.source_url,
                Document.doc_type,
                DocumentSection.section_code,
                DocumentSection.section_title,
                DocumentSubstance.relation,
            )
            .join(Document, Document.id == DocumentSection.document_id)
            .join(ExtractedTextRow, ExtractedTextRow.document_id == Document.id)
            .join(DocumentSubstance, DocumentSubstance.document_id == Document.id)
            .where(
                DocumentSection.document_id.in_(document_ids),
                DocumentSubstance.substance_id == substance_id,
                Document.owner_id.is_(None),
            )
            .order_by(Document.id, DocumentSection.ordinal)
        ).all()
        return _slice_sections(found)

    @staticmethod
    def _has_msds(rows) -> bool:
        """A real MSDS document, not a substance record.

        Kept on section codes rather than `doc_type` even though the two now
        have separate types (2026-08-30): a user upload is `user_upload` and may
        still be a 16-section datasheet, so the section prefix answers the
        question this method actually asks. `has_msds` is what the screen uses
        to explain a mostly-empty card (BR-106).
        """
        return any(
            (row.section_code or "").startswith("msds_")
            and row.relation == SubstanceRelation.SUBJECT.value
            for row in rows
        )

    def _values_for(self, key: CardItemKey, rows) -> list[ItemValue]:
        values = [
            _value(row, ValueOrigin.MSDS)
            for row in rows
            if row.section_code in _MSDS_SECTION_FOR[key]
        ]

        if key is CardItemKey.FIRST_AID:
            # BR-103 / FQ4-7 - the substance API's four routes sit alongside any
            # MSDS section 4, not instead of it. Kept per route because in an
            # incident what matters is which route was exposed.
            values += [
                _value(row, ValueOrigin.SUBSTANCE_API, _ROUTE_SECTION[row.section_code])
                for row in rows
                if row.section_code in _ROUTE_SECTION
            ]

        if key is CardItemKey.REGULATIONS:
            values += [
                _value(row, ValueOrigin.LAW)
                for row in rows
                if row.doc_type == DocType.LAW.value
            ]

        return values


@dataclass(frozen=True)
class _SectionRow:
    """A folded document's section, shaped like a chunk row so `_value` and
    everything after it cannot tell the two apart."""

    text: str
    id: int
    title: str | None
    source_url: str
    doc_type: str
    section_code: str | None
    section_title: str | None
    relation: str
    section_id: int | None = None


def _folded_candidates(rows) -> set[int]:
    """Documents none of whose chunks carries a section.

    A document with even one sectioned chunk was not folded, and reading its
    sections again would put every value on the card twice. Whether a
    candidate has sections at all is decided by the section query: an
    unstructured document has none and keeps its chunks.
    """
    sectioned = {row.id for row in rows if row.section_id is not None}
    return {row.id for row in rows} - sectioned


def _slice_sections(found) -> list[_SectionRow]:
    rows = []
    for row in found:
        # BR-104 - the source text as sliced; only surrounding whitespace goes.
        text = row.full_text[row.start_offset : row.end_offset].strip()
        if not text:
            continue
        rows.append(
            _SectionRow(
                text=text,
                id=row.id,
                title=row.title,
                source_url=row.source_url,
                doc_type=row.doc_type,
                section_code=row.section_code,
                section_title=row.section_title,
                relation=row.relation,
            )
        )
    return rows


def _unfold(chunk_rows, section_rows) -> list:
    """Chunk rows, with each folded document's chunks replaced by its sections.

    Replaced rather than added to: the folded chunk is the same text again.
    Document order is kept.
    """
    by_document: dict[int, list] = {}
    for row in section_rows:
        by_document.setdefault(row.id, []).append(row)
    out: list = []
    unfolded: set[int] = set()
    for row in chunk_rows:
        if row.id not in by_document:
            out.append(row)
        elif row.id not in unfolded:
            unfolded.add(row.id)
            out.extend(by_document[row.id])
    return out


def _value(row, origin: ValueOrigin, route: ExposureRoute | None = None) -> ItemValue:
    return ItemValue(
        # BR-104 - the source text, unedited. Summarising it would put our words
        # where the reader expects the document's.
        text=row.text,
        document_id=row.id,
        document_title=row.title,
        section_code=row.section_code,
        section_title=row.section_title,
        source_url=row.source_url,
        origin=origin,
        route=route,
    )
