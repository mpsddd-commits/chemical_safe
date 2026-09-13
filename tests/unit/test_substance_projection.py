"""Substance master projection — defect 40 (BR-97~99, BR-33).

`SubstanceRepo.upsert()` shipped with u1 and had **zero callers** through u1 and
u2. `stats.substances = 0` read as "nothing collected yet" rather than
"collection does not populate the master", and u1's Build & Test passed over it.

These tests exist so the write path cannot go quiet again.
"""

from __future__ import annotations

import pytest

from app.core.types import SynonymType
from app.substances.projection import SubstanceFacts, extract_facts, project


class FakeRepo:
    """Records what the projection asked for. No database."""

    def __init__(self) -> None:
        self.upserts: list[dict] = []
        self.synonyms: list[tuple] = []
        self.replaced: list[tuple] = []
        self.owned: list[frozenset] = []
        self._by_cas: dict[str, object] = {}

    def upsert(self, *, cas_number=None, **fields):
        if not (cas_number or fields.get("name_ko") or fields.get("name_en")):
            raise ValueError("BR-33")
        self.upserts.append({"cas_number": cas_number, **fields})
        row = self._by_cas.setdefault(cas_number or str(len(self.upserts)), object())
        return row

    def add_synonyms(self, substance, terms):
        self.synonyms.append((substance, terms))
        return len(terms)

    def replace_synonyms(self, substance, terms, *, owned_types):
        self.replaced.append((substance, terms))
        self.owned.append(frozenset(owned_types))
        return len(terms)


REAL_RECORD = {
    "external_id": "1",
    "name_en": "Isopropylamine",
    "name_ko": "이소프로필아민",
    "cas_number": "75-31-0",
    "symptom": "…",
    "inhale": "…",
}


class TestIdentification:
    def test_a_real_record_is_recognised(self):
        facts = extract_facts(REAL_RECORD)
        assert facts is not None
        assert facts.cas_number == "75-31-0"
        assert facts.name_ko == "이소프로필아민"

    @pytest.mark.parametrize(
        "payload",
        [
            None,
            {},
            {"external_id": "1", "text": "본문만 있는 문서"},
            {"cas_number": "", "name_ko": "  ", "name_en": None},
        ],
    )
    def test_a_non_substance_payload_is_not_an_error(self, payload):
        """MSDS PDFs and statutes go through the same indexing path."""
        assert extract_facts(payload) is None

    @pytest.mark.parametrize(
        "payload",
        [
            {"cas_number": "75-31-0"},
            {"name_ko": "이소프로필아민"},
            {"name_en": "Isopropylamine"},
        ],
    )
    def test_any_one_identifier_is_enough(self, payload):
        """BR-33 — at least one of the three."""
        assert extract_facts(payload) is not None

    def test_whitespace_is_not_an_identifier(self):
        assert extract_facts({"cas_number": "   "}) is None


class TestSynonyms:
    def test_only_names_the_source_carries(self):
        """BR-99 — no generated variants.

        A string produced by stripping spaces is not an alias, and `term_type`
        cannot tell the difference once stored — the card would present a name
        nobody published as fact (NFR-8).
        """
        terms = extract_facts(REAL_RECORD).synonym_terms()
        kinds = {kind for _raw, _norm, kind in terms}
        assert kinds == {SynonymType.KO, SynonymType.EN}
        assert SynonymType.ALIAS not in kinds
        assert len(terms) == 2

    def test_normalised_form_travels_with_the_raw_term(self):
        terms = extract_facts({"name_en": "  Isopropylamine  "}).synonym_terms()
        raw, normalized, _kind = terms[0]
        assert raw == "Isopropylamine"
        assert normalized == "isopropylamine"

    def test_a_record_without_names_registers_no_synonyms(self):
        assert extract_facts({"cas_number": "75-31-0"}).synonym_terms() == []


class TestProjection:
    def test_a_substance_record_is_upserted_with_its_synonyms(self):
        repo = FakeRepo()
        assert project(repo, REAL_RECORD) is not None
        assert repo.upserts == [
            {
                "cas_number": "75-31-0",
                "name_ko": "이소프로필아민",
                "name_en": "Isopropylamine",
            }
        ]
        assert len(repo.replaced) == 1

    def test_a_non_substance_payload_writes_nothing(self):
        repo = FakeRepo()
        assert project(repo, {"text": "황산 취급 시…"}) is None
        assert repo.upserts == []
        assert repo.replaced == []

    def test_re_projection_is_idempotent_on_cas(self):
        """BR-98 — a re-index updates rather than duplicates."""
        repo = FakeRepo()
        first = project(repo, REAL_RECORD)
        second = project(repo, REAL_RECORD)
        assert first is second
        assert len({u["cas_number"] for u in repo.upserts}) == 1

    def test_structured_columns_are_left_alone(self):
        """BR-108 — GHS and friends are not derived.

        The source has none of them. Parsing MSDS section 2 into codes would
        store a wrong classification as structured fact; the card quotes the
        text instead, so an error stays checkable against the original.
        """
        repo = FakeRepo()
        project(repo, REAL_RECORD)
        written = repo.upserts[0]
        for column in (
            "ghs_classification",
            "signal_word",
            "h_codes",
            "p_codes",
            "physical_properties",
            "un_number",
        ):
            assert column not in written


class TestFactsContract:
    def test_is_identifiable_matches_br_33(self):
        assert SubstanceFacts("75-31-0", None, None).is_identifiable
        assert SubstanceFacts(None, "이름", None).is_identifiable
        assert SubstanceFacts(None, None, "Name").is_identifiable
        assert not SubstanceFacts(None, None, None).is_identifiable


class TestSourceListMarkers:
    """The source renders names as list items: "·Isopropylamine" (40/40).

    Removing a leading bullet is not the same as generating an alias (BR-99):
    the chemical is called Isopropylamine and the dot is the source's markup.
    """

    def test_leading_bullet_is_removed(self):
        facts = extract_facts({"name_ko": "·아이소프로필아민", "name_en": "·Isopropylamine"})
        assert facts.name_ko == "아이소프로필아민"
        assert facts.name_en == "Isopropylamine"

    def test_hyphens_inside_a_name_survive(self):
        """"3,3-Dimethyl-2-butanone" must come through untouched."""
        facts = extract_facts({"name_en": "·3,3-Dimethyl-2-butanone"})
        assert facts.name_en == "3,3-Dimethyl-2-butanone"

    def test_a_leading_hyphen_is_not_stripped(self):
        """Only bullets are markers here. A hyphen can belong to the name, and
        none were observed as markers - widening the set would edit data."""
        assert extract_facts({"name_en": "-Menthol"}).name_en == "-Menthol"

    def test_a_name_that_is_only_a_marker_is_not_a_name(self):
        assert extract_facts({"name_ko": "·"}) is None

    def test_stripped_name_reaches_the_synonym_term(self):
        raw, normalized, _kind = extract_facts(
            {"name_en": "·Isopropylamine"}
        ).synonym_terms()[0]
        assert raw == "Isopropylamine"
        assert normalized == "isopropylamine"


class TestSynonymsAreReplacedNotAppended:
    """BR-98 — derived data is replaced, the way BR-54 replaces chunks.

    Measured 2026-08-26: after the source's list marker started being stripped,
    a re-index left the table at 160 rows instead of 80 — "·Isopropylamine" sat
    alongside "Isopropylamine" and stayed a live lookup key for a spelling
    nobody should be able to search.
    """

    def test_projection_replaces(self):
        repo = FakeRepo()
        project(repo, REAL_RECORD)
        project(repo, REAL_RECORD)
        assert len(repo.replaced) == 2
        assert repo.synonyms == [], "append path must not be used"

    def test_each_replacement_carries_the_full_set(self):
        repo = FakeRepo()
        project(repo, REAL_RECORD)
        _substance, terms = repo.replaced[0]
        assert len(terms) == 2


class TestDocumentLinkingFromText:
    """Defect 47 — a file has no `cas_number` field, so nothing linked it.

    `document_substance` held exactly one row per substance API record and not
    one row for the eight MSDS PDFs, so a card for 황산 could not reach the two
    황산 datasheets sitting in the same corpus. Collecting the right substances
    (BR-08) does not fix that on its own: the link is the other half.

    The identifier is in the text — "7664-93-9" appears in section 3 of every
    one of these datasheets — so the text is what gets scanned.
    """

    class _Substance:
        def __init__(self, sid, cas, ko, en):
            self.id, self.cas_number, self.name_ko, self.name_en = sid, cas, ko, en

    MASTER = {
        "7664-93-9": _Substance(1, "7664-93-9", "황산", "Sulfuric acid"),
        "108-88-3": _Substance(2, "108-88-3", "톨루엔", "Toluene"),
        "67-56-1": _Substance(3, "67-56-1", "메틸알코올", "Methanol"),
    }

    class _Repo:
        def __init__(self, master):
            self._master = master

        def get_by_cas(self, cas):
            return self._master.get(cas)

    def _service(self):
        from app.services.indexing_service import IndexingService

        service = IndexingService.__new__(IndexingService)
        service._substances = self._Repo(self.MASTER)
        return service

    def _raw(self, payload=None):
        from app.core.types import RawDocument, SourceRef

        ref = SourceRef(source_id="msds_pdf", external_id="x", url="https://e.test/x")
        return RawDocument(ref=ref, payload=payload or {}, media_type="application/pdf")

    def _resolve(self, text, title, payload=None):
        from app.core.types import DocType

        return self._service()._resolve_substances(
            self._raw(payload), DocType.MSDS, text, title
        )

    def test_a_cas_in_the_body_produces_a_link(self):
        from app.core.types import SubstanceRelation

        links = self._resolve("3. 구성성분 황산 7664-93-9 99%", "황산 (SULFURIC ACID) - 남해화학")
        assert links == [(1, SubstanceRelation.SUBJECT)]

    def test_the_title_decides_subject_from_mentioned(self):
        """A mixture datasheet lists fourteen constituents and is about none of them."""
        from app.core.types import SubstanceRelation

        links = self._resolve("톨루엔 108-88-3 5%", "하이큐 프라서페 PS-220 PLUS (혼합물)")
        assert links == [(2, SubstanceRelation.MENTIONED)]

    def test_the_english_title_counts_too(self):
        """"메탄올" is not the master's name for it — "메틸알코올" is."""
        from app.core.types import SubstanceRelation

        links = self._resolve("67-56-1", "메탄올 (Methanol) - Methanex 국문판")
        assert links == [(3, SubstanceRelation.SUBJECT)]

    def test_a_cas_the_master_does_not_carry_is_dropped(self):
        """7647-01-0 (염산) and 7732-18-5 (물) are both in these datasheets."""
        assert self._resolve("7647-01-0 7732-18-5", "염산 (Hydrochloric acid) - 덕산약품") == []

    def test_dates_are_not_read_as_identifiers(self):
        """Every datasheet carries revision dates like 2020-12-01."""
        assert self._resolve("개정일 2020-12-01 작성일 2008-04-01", "황산 - 코리아케미칼") == []

    def test_a_repeated_identifier_links_once(self):
        links = self._resolve("7664-93-9 ... 7664-93-9 ... 7664-93-9", "황산")
        assert len(links) == 1

    def test_a_payload_field_still_wins(self):
        """An API record needs no scanning, and its own CAS is authoritative."""
        from app.core.types import SubstanceRelation

        links = self._resolve("108-88-3", "", payload={"cas_number": "7664-93-9"})
        assert links == [(1, SubstanceRelation.SUBJECT)]

    def test_no_title_is_not_an_error(self):
        from app.core.types import SubstanceRelation

        links = self._resolve("7664-93-9", None)
        assert links == [(1, SubstanceRelation.MENTIONED)]

    def test_empty_text_is_not_an_error(self):
        assert self._resolve("", "황산") == []
