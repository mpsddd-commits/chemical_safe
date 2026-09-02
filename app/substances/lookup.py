"""C49 SubstanceLookup - BR-100, BR-101, BR-109, BR-110.

The rule that shapes this module: **when a name matches several substances, the
system does not choose.** 황산 and 황산구리 are different chemicals, and a user
reading the wrong card has no way to notice. That is R-6, so the ambiguity is
handed back rather than resolved (BR-101).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import MatchKind, SynonymType
from app.db.models import Substance, SubstanceSynonym
from app.processing.stages.normalize import normalize
from app.substances.types import SubstanceRef

CAS_PATTERN = re.compile(r"^\d{2,7}-\d{2}-\d$")
UN_PATTERN = re.compile(r"^UN\s?(\d{4})$", re.IGNORECASE)

# FR-26 asks for five key types. Two have no data behind them, and saying so is
# part of the contract rather than a footnote (BR-109, BR-110).
UNSUPPORTED_KEYS: tuple[str, ...] = (MatchKind.UN.value, MatchKind.ALIAS.value)

_SYNONYM_KIND = {
    SynonymType.KO: MatchKind.NAME_KO,
    SynonymType.EN: MatchKind.NAME_EN,
    SynonymType.ALIAS: MatchKind.ALIAS,
}


class SubstanceLookup:
    def __init__(self, session: Session) -> None:
        self._s = session

    def search(self, raw_query: str) -> list[SubstanceRef]:
        """Returns 0..N candidates. Never picks one (BR-101)."""
        query = normalize(raw_query).strip()
        if not query:
            return []

        if CAS_PATTERN.match(query):
            substance = self._s.scalar(
                select(Substance).where(Substance.cas_number == query)
            )
            return [_ref(substance, MatchKind.CAS)] if substance else []

        un = UN_PATTERN.match(query)
        if un:
            # BR-109 - the path exists and returns nothing, because the source
            # carries no UN numbers. "no data" is the honest answer; removing
            # the path would make an unmet requirement look like it was never
            # asked for.
            substance = self._s.scalar(
                select(Substance).where(Substance.un_number == un.group(1))
            )
            return [_ref(substance, MatchKind.UN)] if substance else []

        return self._by_name(query.lower())

    def _by_name(self, normalized: str) -> list[SubstanceRef]:
        """Substring match on the normalised term.

        Substring rather than exact because "황산" should surface 황산구리 as a
        candidate - the user needs to see the neighbours to know they picked the
        right one. Exact matching would silently answer with one chemical while
        another with a longer name went unmentioned.
        """
        rows = self._s.execute(
            select(SubstanceSynonym, Substance)
            .join(Substance, Substance.id == SubstanceSynonym.substance_id)
            .where(SubstanceSynonym.normalized_term.contains(normalized))
            .order_by(SubstanceSynonym.normalized_term)
        ).all()

        seen: set[int] = set()
        refs: list[SubstanceRef] = []
        for synonym, substance in rows:
            if substance.id in seen:
                continue
            seen.add(substance.id)
            kind = _SYNONYM_KIND.get(
                SynonymType(synonym.term_type), MatchKind.NAME_KO
            )
            refs.append(_ref(substance, kind))
        # Exact matches first: they are what the user most likely meant, and the
        # rest stay visible below rather than being dropped.
        refs.sort(key=lambda r: (not _is_exact(r, normalized), r.display_name))
        return refs

    def get(self, substance_id: int) -> SubstanceRef | None:
        substance = self._s.get(Substance, substance_id)
        return _ref(substance, MatchKind.CAS) if substance else None


def _is_exact(ref: SubstanceRef, normalized: str) -> bool:
    return normalized in {
        (ref.name_ko or "").strip().lower(),
        (ref.name_en or "").strip().lower(),
    }


def _ref(substance: Substance, matched_on: MatchKind) -> SubstanceRef:
    return SubstanceRef(
        substance_id=substance.id,
        cas_number=substance.cas_number,
        name_ko=substance.name_ko,
        name_en=substance.name_en,
        matched_on=matched_on,
    )
