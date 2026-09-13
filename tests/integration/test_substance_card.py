"""Substance master and cards against a live PostgreSQL — u3.

Two of the defects fixed here could not have been caught with a mocked session:

  * **Synonym replacement.** `session.delete()` per child looked right and left
    the table at 0 rows instead of 80, because the relationship carries
    `delete-orphan` and the collection has to be cleared, not emptied item by
    item. A fake repo records the call and says nothing about that.
  * **Defect 40 itself.** The write path existed and nobody called it; only a
    real count shows `substance` sitting at 0 after a full index.
"""

from __future__ import annotations

import glob
import json

import pytest
from sqlalchemy import func, select

from app.core.types import CardItemKey, MatchKind
from app.db.engine import session_scope
from app.db.models import Substance, SubstanceSynonym
from app.db.repositories.catalog import SubstanceRepo
from app.services.substance_service import SubstanceService
from app.substances.projection import project

pytestmark = pytest.mark.integration

def _originals() -> list[str]:
    """The retained substance records (BR-44).

    Two locations because the same test runs in the container (`/data/originals`)
    and on the host through the compose override (`./data/originals`). Skipping
    silently on the host would quietly drop the idempotency check, which is the
    one that caught the synonym accumulation.
    """
    from pathlib import Path

    from app.core.config import get_settings

    roots = [
        Path(get_settings().originals_dir),
        Path(__file__).resolve().parents[2] / "data" / "originals",
    ]
    for root in roots:
        found = sorted(glob.glob(str(root / "ncis_substance" / "*.json")))
        if found:
            return found
    return []


class TestMasterIsPopulated:
    """Defect 40 — BR-33 and BR-37 were never implemented."""

    def test_substances_exist(self):
        with session_scope() as session:
            count = session.scalar(select(func.count()).select_from(Substance))
        assert count > 0, "substance master is empty - defect 40 has regressed"

    def test_every_substance_satisfies_br_33(self):
        with session_scope() as session:
            rows = session.execute(
                select(Substance.cas_number, Substance.name_ko, Substance.name_en)
            ).all()
        assert rows
        for cas, ko, en in rows:
            assert any((cas, ko, en)), "stored a substance with no identifier (BR-33)"

    def test_documents_are_linked(self):
        """BR-37 — `_resolve_substances` matched nothing until the payload fix."""
        from app.db.models import DocumentSubstance

        with session_scope() as session:
            links = session.scalar(select(func.count()).select_from(DocumentSubstance))
        assert links > 0

    def test_chunk_metadata_carries_cas(self):
        """BR-38 needs this populated or exact identifier matching has no target."""
        from app.db.models import ChunkRow

        with session_scope() as session:
            with_cas = session.scalar(
                select(func.count())
                .select_from(ChunkRow)
                .where(ChunkRow.meta["cas_number"].astext.isnot(None))
            )
        assert with_cas > 0


class TestSynonyms:
    def test_only_source_names_are_registered(self):
        """BR-99 (revised 2026-09-13) — every name is printed by its source; none is generated.

        The rule used to be "ko/en only", checked as `kinds <= {"ko", "en"}`.
        It now admits names an MSDS document prints, and the check is stronger
        for it: a name that is not `ko`/`en` must name the document it came
        from, and that document's extracted text (the `normalize()` output every
        offset points into) must contain it verbatim. A string made by removing
        spaces or hyphens, or by joining lines, fails the second half.
        """
        from app.db.models import ExtractedTextRow
        from app.processing.stages.normalize import normalize

        with session_scope() as session:
            rows = session.execute(
                select(
                    SubstanceSynonym.term,
                    SubstanceSynonym.term_type,
                    SubstanceSynonym.source_document_id,
                    ExtractedTextRow.text,
                ).outerjoin(
                    ExtractedTextRow,
                    ExtractedTextRow.document_id == SubstanceSynonym.source_document_id,
                )
            ).all()
        assert rows

        projected = [r for r in rows if r.term_type in {"ko", "en"}]
        printed = [r for r in rows if r.term_type not in {"ko", "en"}]
        # ko/en mirror the substance row, which owns them (migration 0008).
        assert all(r.source_document_id is None for r in projected)

        orphans = [r.term for r in printed if r.source_document_id is None]
        assert not orphans, f"names with no source document: {orphans}"
        generated = [
            (r.term, r.source_document_id)
            for r in printed
            if r.text is None or normalize(r.term) not in r.text
        ]
        assert not generated, f"names their source document does not print: {generated}"

    def test_reindexing_one_msds_leaves_the_other_msds_names(self):
        """Ownership by document, against the real table (rolled back).

        황산 has two MSDS documents. Clearing one document's rows - what a
        re-index does before writing - must leave the other document's rows.
        """
        from app.substances import msds_synonyms

        with session_scope() as session:
            owners = session.execute(
                select(SubstanceSynonym.source_document_id, func.count())
                .where(SubstanceSynonym.source_document_id.isnot(None))
                .group_by(SubstanceSynonym.source_document_id)
                .order_by(SubstanceSynonym.source_document_id)
            ).all()
            if len(owners) < 2:
                pytest.skip("fewer than two MSDS documents own names - re-index MSDS first")
            (cleared, _), *rest = owners
            msds_synonyms.register(SubstanceRepo(session), cleared, None, [], {})
            after = dict(
                session.execute(
                    select(SubstanceSynonym.source_document_id, func.count())
                    .where(SubstanceSynonym.source_document_id.isnot(None))
                    .group_by(SubstanceSynonym.source_document_id)
                ).all()
            )
            session.rollback()
        assert cleared not in after
        assert after == dict(rest)

    def test_an_ambiguous_document_owned_name_does_not_resolve(self):
        """BR-73a - a name another substance's name contains resolves to neither.

        Written and rolled back: a document-owned row equal to another
        substance's `name_ko`. The query side must keep answering with the
        substance whose own name it is, and never with the second one.
        """
        from app.db.models import Document, Substance
        from app.rag.entities import EntityExtractor
        from app.rag.retrieval.retrievers import Retrievers

        with session_scope() as session:
            owner, victim = session.execute(
                select(Substance).where(Substance.name_ko.isnot(None)).order_by(Substance.id)
                .limit(2)
            ).scalars().all()
            document_id = session.scalar(select(Document.id).limit(1))
            session.add(
                SubstanceSynonym(
                    substance_id=owner.id,
                    term=victim.name_ko,
                    normalized_term=victim.name_ko.lower(),
                    term_type="common_name",
                    source_document_id=document_id,
                )
            )
            session.flush()
            owner_cas, victim_cas = owner.cas_number, victim.cas_number
            names = EntityExtractor(session).extract(f"{victim.name_ko} 보호구").substance_names
            cas = Retrievers(session, embedder=None)._cas_for_names(names)
            session.rollback()
        assert cas and owner_cas not in cas
        assert victim_cas in cas

    def test_no_source_list_markers_survive(self):
        """The source renders names as "·Isopropylamine"; the dot is markup."""
        with session_scope() as session:
            stale = session.scalar(
                select(func.count())
                .select_from(SubstanceSynonym)
                .where(SubstanceSynonym.normalized_term.startswith("·"))
            )
        assert stale == 0

    def test_re_projection_does_not_accumulate(self):
        """BR-98 — derived data is replaced, the way BR-54 replaces chunks.

        Appending left "·Isopropylamine" alive next to "Isopropylamine" as a
        lookup key for a spelling nobody should be able to search.
        """
        files = _originals()
        if not files:
            pytest.skip("substance originals not present in this environment")

        with session_scope() as session:
            before = session.scalar(select(func.count()).select_from(SubstanceSynonym))

        for _pass in range(2):
            with session_scope() as session:
                repo = SubstanceRepo(session)
                for path in files:
                    project(repo, json.loads(open(path, encoding="utf-8").read()))

        with session_scope() as session:
            after = session.scalar(select(func.count()).select_from(SubstanceSynonym))
        assert after == before, f"synonyms drifted {before} -> {after}"


class TestCard:
    def _first_id(self) -> int:
        with session_scope() as session:
            return session.scalar(select(Substance.id).order_by(Substance.id).limit(1))

    def test_card_always_has_seven_items_in_order(self):
        """BR-102 — an item is never dropped for being empty."""
        with session_scope() as session:
            card = SubstanceService(session).card(self._first_id())
        assert card is not None
        assert [item.key for item in card.items] == list(CardItemKey)

    def test_missing_count_matches_the_empty_items(self):
        """BR-106 — the caveat travels with the data, not with the template."""
        with session_scope() as session:
            card = SubstanceService(session).card(self._first_id())
        assert card.missing_count == sum(1 for i in card.items if i.is_empty)

    def test_every_value_carries_its_source(self):
        """BR-105 — no value without somewhere to check it."""
        with session_scope() as session:
            card = SubstanceService(session).card(self._first_id())
        values = [v for item in card.items for v in item.values]
        assert values, "expected at least the substance API first-aid routes"
        for value in values:
            assert value.source_url
            assert value.document_id

    def test_first_aid_keeps_routes_separate(self):
        """FQ4-7 — in an incident what matters is which route was exposed."""
        with session_scope() as session:
            card = SubstanceService(session).card(self._first_id())
        first_aid = next(i for i in card.items if i.key is CardItemKey.FIRST_AID)
        routes = {v.route for v in first_aid.values if v.route}
        assert len(routes) >= 3, f"expected several exposure routes, got {routes}"

    def test_unknown_substance_is_none_not_an_error(self):
        with session_scope() as session:
            assert SubstanceService(session).card(10**9) is None


class TestLookup:
    def test_cas_matches_exactly(self):
        with session_scope() as session:
            cas = session.scalar(
                select(Substance.cas_number).where(Substance.cas_number.isnot(None)).limit(1)
            )
            matches, _unsupported = SubstanceService(session).search(cas)
        assert len(matches) == 1
        assert matches[0].matched_on is MatchKind.CAS

    def test_name_search_reports_why_each_candidate_matched(self):
        """BR-101 — picking requires knowing why something is a candidate."""
        with session_scope() as session:
            name = session.scalar(
                select(Substance.name_ko).where(Substance.name_ko.isnot(None)).limit(1)
            )
            matches, _unsupported = SubstanceService(session).search(name)
        assert matches
        assert all(m.matched_on in {MatchKind.NAME_KO, MatchKind.NAME_EN} for m in matches)

    def test_un_lookup_returns_nothing_and_says_so(self):
        """BR-109 — "no data", not "unsupported". The path stays."""
        with session_scope() as session:
            matches, support = SubstanceService(session).search("UN1830")
        assert matches == []
        assert "un" in support.unsupported
        # Alias support is counted from the table (D11), not declared: it is in
        # exactly one of the two lists, or in neither when every substance has one.
        assert not ("alias" in support.unsupported and "alias" in support.partial)

    def test_empty_query_is_not_an_error(self):
        with session_scope() as session:
            matches, _unsupported = SubstanceService(session).search("   ")
        assert matches == []


class TestMsdsDocumentsAreLinked:
    """Defect 47 — the PDFs in the corpus reached no substance at all.

    `document_substance` held one row per substance API record and nothing for
    the eight MSDS PDFs, because the link was read from a payload field and a
    file has none. Collecting the right substances (BR-08, defect 44) puts 황산
    in the master; this is what lets the 황산 card reach the two 황산 datasheets
    that were in the corpus the whole time.
    """

    def _cas(self, cas: str) -> int | None:
        with session_scope() as session:
            return session.scalar(select(Substance.id).where(Substance.cas_number == cas))

    def test_pdf_documents_are_linked_to_substances(self):
        from app.db.models import Document, DocumentSubstance, Source

        with session_scope() as session:
            links = session.scalar(
                select(func.count())
                .select_from(DocumentSubstance)
                .join(Document, Document.id == DocumentSubstance.document_id)
                .join(Source, Source.id == Document.source_id)
                .where(Source.source_id == "msds_pdf")
            )
        assert links > 0, "no MSDS PDF reaches a substance - defect 47 has regressed"

    def test_a_mixture_datasheet_is_not_claimed_as_a_subject(self):
        """It lists fourteen constituents and is the datasheet for none of them."""
        from app.core.types import SubstanceRelation
        from app.db.models import Document, DocumentSubstance

        with session_scope() as session:
            rows = session.execute(
                select(DocumentSubstance.relation)
                .join(Document, Document.id == DocumentSubstance.document_id)
                .where(Document.title.like("%혼합물%"))
            ).all()
        assert all(r[0] == SubstanceRelation.MENTIONED.value for r in rows)

    def test_sulfuric_acid_has_msds_backed_items(self):
        """The card that started defect 44: 황산, six of seven items empty."""
        substance_id = self._cas("7664-93-9")
        if substance_id is None:
            pytest.skip("황산 not in the master - run BR-08 collection first")
        with session_scope() as session:
            card = SubstanceService(session).card(substance_id)
        assert card.has_msds
        assert card.missing_count < 6, "the MSDS sections did not reach the card"
