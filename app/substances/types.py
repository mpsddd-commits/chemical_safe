"""Value objects V1~V3 - alive for one request, never persisted.

u3 adds no tables. The three it needs shipped with u1 and were pre-provisioned
for exactly this (DD-21, UD-6); what was missing was the write path, not the
schema (defect 40).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.types import CardItemKey, ExposureRoute, MatchKind, ValueOrigin

# FR-24's seven items, in the order a card always shows them (BR-102).
ITEM_LABELS: dict[CardItemKey, str] = {
    CardItemKey.GHS: "GHS 분류 및 신호어",
    CardItemKey.HP_CODES: "H·P 문구",
    CardItemKey.PHYSICAL: "물리화학적 성질",
    CardItemKey.PPE: "권장 개인보호구",
    CardItemKey.FIRST_AID: "응급조치 요령",
    CardItemKey.STORAGE: "저장·취급 주의사항",
    CardItemKey.REGULATIONS: "적용 법령",
}

NO_DATA = "정보 없음"


@dataclass
class SubstanceRef:
    """V1 - one lookup candidate.

    `matched_on` is here because when a name matches several substances the user
    picks (BR-101), and picking requires knowing *why* each is a candidate.
    Searching 황산 and getting 황산구리 back should be visible as that.
    """

    substance_id: int
    cas_number: str | None
    name_ko: str | None
    name_en: str | None
    matched_on: MatchKind

    @property
    def display_name(self) -> str:
        return self.name_ko or self.name_en or self.cas_number or f"#{self.substance_id}"


@dataclass
class ItemValue:
    """One sourced value inside a card item.

    Several may back one item and all of them are shown (BR-103): when two MSDS
    prescribe different protective equipment, that disagreement is itself
    something the reader needs, and choosing one hides it.
    """

    text: str
    document_id: int
    document_title: str | None
    section_code: str | None
    section_title: str | None
    source_url: str
    origin: ValueOrigin
    # First aid only - which exposure route this value covers (BR-103, FQ4-7).
    route: ExposureRoute | None = None


@dataclass
class CardItem:
    """V2 - one of the seven. `values` being empty is a normal state.

    Most of the 40 substances have no MSDS, so six of seven items are empty for
    them. The screen renders that as "정보 없음" and never drops the item
    (BR-102, BR-106).
    """

    key: CardItemKey
    values: list[ItemValue] = field(default_factory=list)

    @property
    def label(self) -> str:
        return ITEM_LABELS[self.key]

    @property
    def is_empty(self) -> bool:
        return not self.values


@dataclass
class SubstanceCard:
    """V3 - always seven items, always in order."""

    substance: SubstanceRef
    items: list[CardItem]
    has_msds: bool = False

    @property
    def missing_count(self) -> int:
        """BR-106 - carried on the object so a template cannot forget it.

        The same device as u2's `unpriced_calls` (BR-96) and `removed` (BR-88):
        the caveat travels with the data rather than being recomputed by
        whoever displays it.
        """
        return sum(1 for item in self.items if item.is_empty)
