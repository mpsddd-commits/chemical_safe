"""SubstanceRepo and SourceRepo.

Repositories are the only place a Session is touched. Domain components receive
a repository, never a session (DD-20), which keeps chunking / retry / structure
logic unit-testable without a database (NFR-24, NFR-28).
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import PolicyDecision, SynonymType
from app.db.models import PolicyCheck, Source, Substance, SubstanceSynonym


class SourceRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, source_id: str) -> Source | None:
        return self._s.scalar(select(Source).where(Source.source_id == source_id))

    def list_all(self) -> list[Source]:
        return list(self._s.scalars(select(Source).order_by(Source.source_id)))

    def upsert(self, **fields: object) -> Source:
        existing = self.get(str(fields["source_id"]))
        if existing is None:
            existing = Source(**fields)  # type: ignore[arg-type]
            self._s.add(existing)
        else:
            for key, value in fields.items():
                setattr(existing, key, value)
        self._s.flush()
        return existing

    def record_policy(
        self,
        source: Source | None,
        url: str,
        decision: PolicyDecision,
        reason: str | None,
        checked_at: datetime,
    ) -> None:
        """CON-3 - the fact that a blocked source was *not* collected is itself
        an auditable record."""
        self._s.add(
            PolicyCheck(
                source_id=source.id if source else None,
                url=url,
                decision=decision.value,
                reason=reason,
                checked_at=checked_at,
            )
        )
        if source is not None:
            source.policy_status = decision.value
            source.policy_reason = reason
            source.policy_checked_at = checked_at
        self._s.flush()

    def mark_collected(self, source: Source, when: datetime) -> None:
        """BR-13 - only advanced on succeeded/partial so a failed run re-covers
        the same window next time."""
        source.last_collected_at = when
        self._s.flush()


class SubstanceRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get_by_id(self, substance_id: int) -> Substance | None:
        return self._s.get(Substance, substance_id)

    def get_by_cas(self, cas: str) -> Substance | None:
        return self._s.scalar(select(Substance).where(Substance.cas_number == cas))

    def find_by_normalized_term(self, normalized: str) -> Substance | None:
        """Backs u3 synonym resolution. Present in u1 because the synonym rows
        are written at collection time (DD-21)."""
        row = self._s.scalar(
            select(SubstanceSynonym).where(SubstanceSynonym.normalized_term == normalized)
        )
        return row.substance if row else None

    def upsert(self, *, cas_number: str | None = None, **fields: object) -> Substance:
        """BR-33 - a substance must carry at least one identifier."""
        if not (cas_number or fields.get("name_ko") or fields.get("name_en")):
            raise ValueError("substance requires cas_number, name_ko or name_en (BR-33)")
        existing = self.get_by_cas(cas_number) if cas_number else None
        if existing is None:
            existing = Substance(cas_number=cas_number, **fields)  # type: ignore[arg-type]
            self._s.add(existing)
        else:
            for key, value in fields.items():
                if value is not None:
                    setattr(existing, key, value)
        self._s.flush()
        return existing

    def replace_synonyms(
        self,
        substance: Substance,
        terms: list[tuple[str, str, SynonymType]],
        *,
        owned_types: Collection[SynonymType],
    ) -> int:
        """Replace the synonyms of the types this caller produces (BR-98).

        `add_synonyms` only skips exact duplicates, so a change in how names are
        derived leaves the old rows behind. Measured 2026-08-26: after the source
        list marker was stripped, the table held 160 rows instead of 80 -
        "·Isopropylamine" sat alongside "Isopropylamine" and would still match a
        lookup nobody should be able to make.

        Same reasoning as BR-54 for chunks: derived data is replaced, not
        accumulated, or a re-index stops being idempotent.

        **Only `owned_types` are replaced.** The table has more than one
        producer: the NCIS projection writes `ko`/`en`, and
        `scripts/backfill_synonyms.py` writes `msds_title`/`common_name`/
        `formula` (D11). Clearing every type let a re-index silently delete the
        backfill - one job destroying another job's premise, the same shape as
        the resume path that destroyed its own precondition (`runner.py`).

        `owned_types` is keyword-only and has **no default**. A default of "all
        types" would hand the next caller the same accident; a default of "the
        projection's types" would make a second producer replace someone else's
        rows. Saying which rows you own is the price of deleting any.
        """
        owned = frozenset(owned_types)
        if not owned:
            raise ValueError("owned_types must name at least one SynonymType")
        foreign = sorted({kind.value for _raw, _norm, kind in terms} - {k.value for k in owned})
        if foreign:
            # A term of a type the caller does not own would never be replaced
            # by this caller again - it would accumulate exactly as BR-98 forbids.
            raise ValueError(f"terms carry types outside owned_types: {foreign}")

        owned_values = {kind.value for kind in owned}
        # Remove from the collection, not `session.delete()` per child. The
        # relationship carries `delete-orphan`, so leaving the collection is what
        # removes the rows; deleting the objects individually left them in the
        # collection, and the append that followed was wiped along with them -
        # measured, the table went to 0 rows instead of 80.
        for row in [s for s in substance.synonyms if s.term_type in owned_values]:
            substance.synonyms.remove(row)
        self._s.flush()
        return self.add_synonyms(substance, terms)

    def add_synonyms(
        self, substance: Substance, terms: list[tuple[str, str, SynonymType]]
    ) -> int:
        """``terms`` is (raw term, normalized term, type). Duplicates are skipped."""
        seen = {
            (s.normalized_term, s.term_type) for s in substance.synonyms
        }
        added = 0
        for raw, normalized, kind in terms:
            key = (normalized, kind.value)
            if not normalized or key in seen:
                continue
            substance.synonyms.append(
                SubstanceSynonym(term=raw, normalized_term=normalized, term_type=kind.value)
            )
            seen.add(key)
            added += 1
        self._s.flush()
        return added

    def count(self) -> int:
        return self._s.scalar(select(func.count()).select_from(Substance)) or 0
