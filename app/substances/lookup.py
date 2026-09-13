"""C49 SubstanceLookup - BR-100, BR-101, BR-109, BR-110.

The rule that shapes this module: **when a name matches several substances, the
system does not choose.** 황산 and 황산구리 are different chemicals, and a user
reading the wrong card has no way to notice. That is R-6, so the ambiguity is
handed back rather than resolved (BR-101).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.types import MatchKind, SynonymType
from app.db.models import Substance, SubstanceSynonym
from app.processing.stages.normalize import normalize
from app.substances.types import SubstanceRef

CAS_PATTERN = re.compile(r"^\d{2,7}-\d{2}-\d$")
UN_PATTERN = re.compile(r"^UN\s?(\d{4})$", re.IGNORECASE)

# FR-26 asks for five key types. UN numbers have no data behind them, and saying
# so is part of the contract rather than a footnote (BR-109).
UNSUPPORTED_KEYS: tuple[str, ...] = (MatchKind.UN.value,)

_SYNONYM_KIND = {
    SynonymType.KO: MatchKind.NAME_KO,
    SynonymType.EN: MatchKind.NAME_EN,
    SynonymType.ALIAS: MatchKind.ALIAS,
    # D11 backfill: a published other name is an alias, not the master's
    # name_ko - falling through to the NAME_KO default would say otherwise.
    SynonymType.MSDS_TITLE: MatchKind.ALIAS,
    SynonymType.COMMON_NAME: MatchKind.ALIAS,
    SynonymType.FORMULA: MatchKind.ALIAS,
}

# Derived from the map above, so a synonym type that starts answering as an
# alias is counted as one without a second list to keep in step.
ALIAS_SYNONYM_TYPES: frozenset[SynonymType] = frozenset(
    kind for kind, match in _SYNONYM_KIND.items() if match is MatchKind.ALIAS
)


@dataclass(frozen=True)
class KeySupport:
    """Which FR-26 key types the data behind the search can answer (BR-109, BR-110).

    Three states, because two were a lie in one direction or the other. Alias
    rows now exist for some substances (D11): calling aliases unsupported
    under-claims (H2SO4 finds 황산), and dropping the notice over-claims (most
    substances carry no alias at all). `partial` says the key works where the
    data exists and not everywhere.
    """

    unsupported: tuple[str, ...]
    partial: tuple[str, ...]


def classify_alias(substances: int, with_alias: int) -> str | None:
    """`"unsupported"`, `"partial"`, or None when every substance has an alias.

    Counted at request time rather than written into a sentence: a number in
    the notice becomes false the day an alias is added (the reason D10 took
    "49종" out of the refusal text).
    """
    if with_alias <= 0:
        return "unsupported"
    if with_alias < substances:
        return "partial"
    return None


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

    def key_support(self) -> KeySupport:
        """What the table can answer right now, counted, not assumed."""
        substances = self._s.scalar(select(func.count()).select_from(Substance)) or 0
        with_alias = (
            self._s.scalar(
                select(func.count(distinct(SubstanceSynonym.substance_id))).where(
                    SubstanceSynonym.term_type.in_(
                        sorted(kind.value for kind in ALIAS_SYNONYM_TYPES)
                    )
                )
            )
            or 0
        )
        unsupported = list(UNSUPPORTED_KEYS)
        partial: list[str] = []
        state = classify_alias(substances, with_alias)
        if state == "unsupported":
            unsupported.append(MatchKind.ALIAS.value)
        elif state == "partial":
            partial.append(MatchKind.ALIAS.value)
        return KeySupport(unsupported=tuple(unsupported), partial=tuple(partial))

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
