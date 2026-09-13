"""SubstanceRepo and SourceRepo.

Repositories are the only place a Session is touched. Domain components receive
a repository, never a session (DD-20), which keeps chunking / retry / structure
logic unit-testable without a database (NFR-24, NFR-28).
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.core.types import PolicyCheckScope, PolicyDecision, SynonymType
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
        an auditable record.

        This is the check of the source's `base_url` only (D8). It gates job
        creation and feeds `source.policy_*`; it is not the verdict for the
        hosts the documents come from - see `record_document_origin_policy`.
        """
        self._s.add(
            PolicyCheck(
                source_id=source.id if source else None,
                scope=PolicyCheckScope.SOURCE_BASE_URL.value,
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

    def record_document_origin_policy(
        self,
        source: Source,
        job_id: int,
        origin: str,
        decision: PolicyDecision,
        reason: str | None,
        checked_at: datetime,
    ) -> None:
        """D8 - a verdict the orchestrator enforced on a document origin in a job.

        `source.policy_*` is deliberately left alone. That state gates the
        collect button for the whole source, and one vendor host refusing its
        documents does not make the source itself uncollectable - those
        documents already fail as `policy_blocked` items.
        """
        self._s.add(
            PolicyCheck(
                source_id=source.id,
                scope=PolicyCheckScope.DOCUMENT_ORIGIN.value,
                job_id=job_id,
                url=origin,
                decision=decision.value,
                reason=reason,
                checked_at=checked_at,
            )
        )
        self._s.flush()

    def latest_document_origin_checks(self, source: Source) -> list[PolicyCheck]:
        """The document-origin verdicts of the most recent job that recorded any."""
        latest_job = self._s.scalar(
            select(func.max(PolicyCheck.job_id)).where(
                PolicyCheck.source_id == source.id,
                PolicyCheck.scope == PolicyCheckScope.DOCUMENT_ORIGIN.value,
            )
        )
        if latest_job is None:
            return []
        return list(
            self._s.scalars(
                select(PolicyCheck)
                .where(
                    PolicyCheck.source_id == source.id,
                    PolicyCheck.scope == PolicyCheckScope.DOCUMENT_ORIGIN.value,
                    PolicyCheck.job_id == latest_job,
                )
                .order_by(PolicyCheck.url, PolicyCheck.checked_at)
            )
        )

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
        source_document_id: int | None,
    ) -> int:
        """Replace the synonyms this caller owns (BR-98).

        `add_synonyms` only skips exact duplicates, so a change in how names are
        derived leaves the old rows behind. Measured 2026-08-26: after the source
        list marker was stripped, the table held 160 rows instead of 80 -
        "·Isopropylamine" sat alongside "Isopropylamine" and would still match a
        lookup nobody should be able to make.

        Same reasoning as BR-54 for chunks: derived data is replaced, not
        accumulated, or a re-index stops being idempotent.

        **A caller owns rows by document and by type, both stated.**

        * `source_document_id` - the document that published the names, or None
          for the substance-owned `ko`/`en` rows the NCIS projection mirrors from
          `substance.name_ko`/`name_en`. Owning by type alone was right while
          each type had one producer, and wrong for MSDS names: 황산 has two MSDS
          documents, and re-indexing one while replacing every `common_name`
          of the substance would delete what the other one printed (D11
          follow-up, 2026-09-13). Only rows whose `source_document_id` equals
          this one are touched - None matches None and nothing else.
        * `owned_types` - kept alongside the document. The NULL owner is shared
          by every substance-owned type (`ko`/`en` today, `cas`/`un` if they
          are ever filled), and a document may one day carry a second producer;
          the type set is what stops either from replacing the other's rows.

        Both are keyword-only and have **no default**. A default document of
        None would let an MSDS caller that forgot it replace the projection's
        rows; a default type set would hand the next caller someone else's rows.
        Saying which rows you own is the price of deleting any.
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
        for row in [
            s
            for s in substance.synonyms
            if s.term_type in owned_values and s.source_document_id == source_document_id
        ]:
            substance.synonyms.remove(row)
        self._s.flush()
        return self.add_synonyms(substance, terms, source_document_id=source_document_id)

    def replace_document_synonyms(
        self,
        document_id: int,
        entries: list[tuple[Substance, list[tuple[str, str, SynonymType]]]],
        *,
        owned_types: Collection[SynonymType],
    ) -> int:
        """Replace every row `document_id` owns, across substances.

        `replace_synonyms` works on one substance's collection. A document whose
        subject changed, or that stopped being a single-subject MSDS, still owns
        rows on the substance it used to name; those go too, or they would
        outlive the evidence for them. An empty `entries` clears the document.
        """
        owned = frozenset(owned_types)
        if not owned:
            raise ValueError("owned_types must name at least one SynonymType")
        keep = {substance.id for substance, _terms in entries}
        stale = self._s.scalars(
            select(SubstanceSynonym).where(
                SubstanceSynonym.source_document_id == document_id,
                SubstanceSynonym.term_type.in_(sorted(kind.value for kind in owned)),
                SubstanceSynonym.substance_id.not_in(keep) if keep else true(),
            )
        ).all()
        for row in stale:
            row.substance.synonyms.remove(row)
        self._s.flush()
        added = 0
        for substance, terms in entries:
            added += self.replace_synonyms(
                substance, terms, owned_types=owned, source_document_id=document_id
            )
        return added

    def add_synonyms(
        self,
        substance: Substance,
        terms: list[tuple[str, str, SynonymType]],
        *,
        source_document_id: int | None,
    ) -> int:
        """``terms`` is (raw term, normalized term, type). Duplicates are skipped.

        A duplicate is the same name, type and owner. The same name from two
        documents is two rows: each is evidence the other cannot vouch for.
        """
        seen = {
            (s.normalized_term, s.term_type, s.source_document_id) for s in substance.synonyms
        }
        added = 0
        for raw, normalized, kind in terms:
            key = (normalized, kind.value, source_document_id)
            if not normalized or key in seen:
                continue
            substance.synonyms.append(
                SubstanceSynonym(
                    term=raw,
                    normalized_term=normalized,
                    term_type=kind.value,
                    source_document_id=source_document_id,
                )
            )
            seen.add(key)
            added += 1
        self._s.flush()
        return added

    def projected_names(self) -> tuple[dict[int, list[str]], dict[int, str]]:
        """Every substance's ko/en synonym terms, and a label per substance.

        What MSDS name screening compares against: a name equal to or inside a
        substance's own name adds nothing, and one inside another substance's
        name resolves to the wrong one (`app/substances/msds_synonyms.py`).
        """
        labels: dict[int, str] = {}
        names: dict[int, list[str]] = {}
        for sid, ko, en in self._s.execute(
            select(Substance.id, Substance.name_ko, Substance.name_en).order_by(Substance.id)
        ).all():
            labels[sid] = ko or en or str(sid)
            names[sid] = []
        for sid, term in self._s.execute(
            select(SubstanceSynonym.substance_id, SubstanceSynonym.term).where(
                SubstanceSynonym.term_type.in_([SynonymType.KO.value, SynonymType.EN.value])
            )
        ).all():
            names.setdefault(sid, []).append(term)
        return names, labels

    def count(self) -> int:
        return self._s.scalar(select(func.count()).select_from(Substance)) or 0
