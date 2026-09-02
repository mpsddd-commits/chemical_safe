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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import CardItemKey, DocType, ExposureRoute, SubstanceRelation, ValueOrigin
from app.db.models import ChunkRow, Document, DocumentSection, DocumentSubstance
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
        """
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
