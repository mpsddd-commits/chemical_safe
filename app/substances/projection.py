"""Substance master projection - defect 40 (BR-97~99, BR-33, BR-37).

This is u1's rule (BR-33, traced to FR-1) implemented at last. `SubstanceRepo`
and the three tables shipped with u1; **only the write path was missing**, and
`SubstanceRepo.upsert()` had zero callers for the whole of u1 and u2.

It runs **inside the indexing path** (BR-97) rather than as a separate backfill
command, and that placement is the lesson from the defect itself: a write path
detached from indexing is a write path nobody calls. `stats.substances = 0` then
reads as "nothing collected yet" instead of "collection does not populate the
master", which is exactly how u1's Build & Test passed over it.

Two details are measured, not assumed:

  * **The record is read from `raw.payload`, not `ref.extra`.** The list adapter
    puts the row under `extra["row"]` while `_resolve_substances` looked for a
    top-level `extra["cas_number"]` - so even the *read* side never matched.
    `payload` is the same place for a fresh fetch and for a re-index from the
    retained original (BR-44).
  * **No source id is hard-coded.** Substance records arrive as `doc_type=msds`
    from `ncis_substance`, alongside genuine MSDS PDFs from `msds_pdf`. The test
    is whether the payload carries what BR-33 requires, so adding a source later
    changes no code.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.types import SynonymType

log = get_logger(__name__)

@dataclass(frozen=True)
class SubstanceFacts:
    """What a payload actually tells us about a substance.

    Deliberately small. GHS, signal word, H/P codes and physical properties have
    columns on `substance` and are **not** filled (BR-108): the source has none
    of them, and deriving them would mean parsing MSDS section 2 into codes -
    where a parsing slip stores a wrong GHS classification as structured fact.
    The card quotes the MSDS text instead, so an error stays checkable.
    """

    cas_number: str | None
    name_ko: str | None
    name_en: str | None

    @property
    def is_identifiable(self) -> bool:
        """BR-33 - at least one of `cas_number`, `name_ko`, `name_en`."""
        return any((self.cas_number, self.name_ko, self.name_en))

    def synonym_terms(self) -> list[tuple[str, str, SynonymType]]:
        """BR-99 - only names the source actually carries.

        No generated variants. A string we produced by stripping spaces is not
        an alias, and `term_type` cannot tell the difference once it is stored -
        the card would present a name nobody published as fact (NFR-8).
        """
        terms: list[tuple[str, str, SynonymType]] = []
        if self.name_ko:
            terms.append((self.name_ko, _normalize_term(self.name_ko), SynonymType.KO))
        if self.name_en:
            terms.append((self.name_en, _normalize_term(self.name_en), SynonymType.EN))
        return terms


def _normalize_term(term: str) -> str:
    """Lookup uses the same normalisation the index used (BR-100)."""
    from app.processing.stages.normalize import normalize

    return normalize(term).strip().lower()


# The list marker the source actually prefixes names with: "·Isopropylamine",
# measured on all 40 records. Bullet characters only - a hyphen or asterisk is
# deliberately **not** stripped, because those occur inside real chemical names
# and were never observed as markers here. Guessing wider would edit data.
_LEADING_MARKERS = "·•‧・∙"


def _clean(value: object) -> str | None:
    """Trim whitespace and the source's leading list marker.

    Stripping a bullet is **not** the same as generating an alias (BR-99).
    "·Isopropylamine" is the source's rendering of a list item; the chemical is
    called Isopropylamine. Only a *leading* marker is removed - nothing inside
    the name is touched, so "3,3-Dimethyl-2-butanone" survives intact.
    """
    if value is None:
        return None
    text = str(value).strip().lstrip(_LEADING_MARKERS).strip()
    return text or None


def extract_facts(payload: dict | None) -> SubstanceFacts | None:
    """Read a substance record. Returns None when this is not one.

    A missing payload, or one carrying none of BR-33's identifying fields, is
    not an error: MSDS PDFs and statutes go through the same indexing path and
    simply are not substance records.
    """
    if not payload:
        return None
    facts = SubstanceFacts(
        cas_number=_clean(payload.get("cas_number")),
        name_ko=_clean(payload.get("name_ko")),
        name_en=_clean(payload.get("name_en")),
    )
    if not facts.is_identifiable:
        return None
    return facts


def project(repo, payload: dict | None):
    """BR-97/98/99 - upsert the substance and its real names.

    Keyed on CAS so a re-index updates rather than duplicates (BR-98). Returns
    the `Substance` row, or None when the payload is not a substance record.
    """
    facts = extract_facts(payload)
    if facts is None:
        return None

    substance = repo.upsert(
        cas_number=facts.cas_number,
        name_ko=facts.name_ko,
        name_en=facts.name_en,
    )
    terms = facts.synonym_terms()
    if terms:
        # Replace, not append (BR-98). Appending let a change in name handling
        # leave the previous spelling behind as a live lookup key.
        repo.replace_synonyms(substance, terms)
    log.info(
        "substance_projected",
        extra={"cas_number": facts.cas_number, "synonyms": len(terms)},
    )
    return substance
