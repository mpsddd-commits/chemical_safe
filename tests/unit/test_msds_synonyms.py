"""BR-97/99 (revised 2026-09-13) - the names an MSDS document prints, chosen in the index path.

The rules moved here from `scripts/backfill_synonyms.py` (D11), which BR-97
forbids: a re-index from the originals did not run it. The table is matched by
substring (`normalized_term in query`), so a wrong row resolves a question to the
wrong substance. These pin the exclusions that stop that, the revised BR-99
gate - a name the document does not print verbatim is a string we made - and
that a document only ever writes its own rows.
"""

from __future__ import annotations

import pytest

from app.core.types import MatchKind, SynonymType
from app.substances import msds_synonyms as ms

DOC = 900
SULFURIC, MEK, DIMETHYLBUTANONE, TBA = 47, 49, 11, 9
BASE = {
    SULFURIC: ["황산", "Sulfuric acid"],
    MEK: ["메틸 에틸 케톤", "Methyl ethyl ketone"],
    DIMETHYLBUTANONE: ["3,3-다이메틸-2-뷰탄온", "3,3-Dimethyl-2-butanone"],
    TBA: ["3차-뷰틸아민", "tert-Butylamine"],
}


def _verdicts(result):
    return {(c.substance_id, c.term): c.reason for c in result}


def _cand(sid, term, term_type=None, pair=None, doc=DOC):
    return ms.Candidate(sid, doc, term, term_type or ms.COMMON_NAME, ["test"], pair=pair)


class TestAmbiguity:
    def test_a_term_inside_another_substances_name_is_excluded(self):
        # "2-Butanone" is printed for MEK, and sits inside 3,3-dimethyl-2-butanone.
        result = ms.screen([_cand(MEK, "2-Butanone")], BASE)
        reason = _verdicts(result)[(MEK, "2-Butanone")]
        assert reason is not None and reason.startswith("모호")

    def test_a_term_two_substances_both_claim_is_excluded_for_both(self):
        result = ms.screen([_cand(SULFURIC, "Oil of vitriol"), _cand(MEK, "Oil of vitriol")], BASE)
        verdicts = _verdicts(result)
        assert verdicts[(SULFURIC, "Oil of vitriol")].startswith("모호")
        assert verdicts[(MEK, "Oil of vitriol")].startswith("모호")

    def test_the_gloss_of_an_ambiguous_name_goes_with_it(self):
        result = ms.screen(
            [_cand(MEK, "2-뷰타논", pair="p"), _cand(MEK, "2-Butanone", pair="p")], BASE
        )
        assert _verdicts(result)[(MEK, "2-뷰타논")] == "모호해서 제외 (짝 표기가 모호)"


class TestShortAndGeneric:
    @pytest.mark.parametrize(
        ("term", "fragment"),
        [("유산", "너무 짧음 (2자)"), ("NH3", "라틴 3자"), ("AIBN", "라틴 4자")],
    )
    def test_short_tokens_are_excluded(self, term, fragment):
        reason = _verdicts(ms.screen([_cand(SULFURIC, term)], BASE))[(SULFURIC, term)]
        assert reason is not None and fragment in reason

    def test_a_five_letter_formula_is_long_enough(self):
        result = ms.screen([_cand(SULFURIC, "H2SO4", ms.FORMULA)], BASE)
        assert _verdicts(result)[(SULFURIC, "H2SO4")] is None

    @pytest.mark.parametrize("term", ["혼합물", "자료없음", "Solution"])
    def test_generic_nouns_are_excluded(self, term):
        reason = _verdicts(ms.screen([_cand(SULFURIC, term)], BASE))[(SULFURIC, term)]
        assert reason == "일반 명사"

    def test_company_names_are_excluded(self):
        result = ms.screen([_cand(SULFURIC, "남해화학 여수")], BASE, companies=["남해화학"])
        assert _verdicts(result)[(SULFURIC, "남해화학 여수")] == "회사명"


class TestExistingNames:
    def test_the_existing_name_is_not_written_again(self):
        result = ms.screen([_cand(SULFURIC, "SULFURIC ACID", ms.MSDS_TITLE)], BASE)
        assert _verdicts(result)[(SULFURIC, "SULFURIC ACID")] == "기존 이름과 같음"

    def test_a_broader_name_inside_the_existing_one_is_excluded(self):
        # Daejung prints "Butylamine" as a synonym of tert-Butylamine.
        reason = _verdicts(ms.screen([_cand(TBA, "Butylamine")], BASE))[(TBA, "Butylamine")]
        assert reason is not None and reason.startswith("기존 이름의 일부")

    def test_a_spacing_variant_the_document_prints_is_kept(self):
        base = {45: ["메틸알코올", "Methanol"]}
        result = ms.screen([_cand(45, "메틸 알코올")], base)
        assert _verdicts(result)[(45, "메틸 알코올")] is None


class TestOneRowPerNamePerDocument:
    def test_one_row_per_name_even_from_two_sources_in_one_document(self):
        result = ms.screen(
            [_cand(45, "메탄올", ms.MSDS_TITLE), _cand(45, "메탄올", ms.COMMON_NAME)],
            {45: ["메틸알코올"]},
        )
        assert len(result) == 1 and result[0].term_type == ms.COMMON_NAME
        assert result[0].evidence == ["test"]

    def test_two_documents_printing_one_name_each_keep_theirs(self):
        """Each document owns its row; merging them would leave one without evidence."""
        result = ms.screen(
            [_cand(45, "메탄올", doc=25), _cand(45, "메탄올", doc=26)], {45: ["메틸알코올"]}
        )
        assert sorted((c.document_id, c.reason) for c in result) == [(25, None), (26, None)]


class TestExcludedTerms:
    """A misprint in the source is not a synonym, and a re-index must not bring it back."""

    FORMAMIDE = 4
    BASE = {FORMAMIDE: ["폼아마이드", "Formamide"]}

    def test_the_formamide_misprint_is_excluded_with_its_reason(self):
        result = ms.screen(
            [_cand(self.FORMAMIDE, "Formanfide"), _cand(self.FORMAMIDE, "Methanamide")], self.BASE
        )
        verdicts = _verdicts(result)
        assert verdicts[(self.FORMAMIDE, "Formanfide")] == "원문 오타 (Formamide 의 오기)"
        assert verdicts[(self.FORMAMIDE, "Methanamide")] is None


class TestExtraction:
    def test_only_the_row_with_this_substances_cas_counts(self):
        text = (
            "관용명및이명 Chlorine\nCAS번호 7782-50-5\n"
            "관용명및이명 물, 산화이수소\nCAS번호 7732-18-5\n"
        )
        rows = ms.labeled_values(text, "7782-50-5")
        assert rows[0][:2] == ("Chlorine", None)
        assert rows[1][1] == "다른 성분의 행 (CAS 7732-18-5)"

    def test_an_inverted_index_name_is_not_split_into_two_names(self):
        # HEXANEDIOIC ACID is adipic acid - a different substance.
        out = dict(ms.split_value("HEXANEDIOIC ACID, BIS(2-ETHYLHEXYL)ESTER"))
        assert out["HEXANEDIOIC ACID"] is not None
        assert out["BIS(2-ETHYLHEXYL)ESTER"] is not None

    def test_locant_commas_do_not_split(self):
        out = dict(ms.split_value("Isopropylamine,2-Propylamine,Propane,2-amino-"))
        assert out["2-Propylamine"] is None
        assert out["Propane"] is not None  # head of "Propane, 2-amino-"

    def test_a_gloss_yields_both_names(self):
        assert ms.split_value("2-뷰타논(2-Butanone)") == [("2-뷰타논", None), ("2-Butanone", None)]

    def test_title_drops_the_company(self):
        assert ms.title_names("메탄올 (Methanol) - Methanex 국문판") == (
            ["메탄올", "Methanol"],
            "Methanex 국문판",
        )

    def test_formula_label_value_loses_its_hyphens(self):
        assert ms.formula_values("분자식: H2-S-O4") == ["H2SO4"]
        assert ms.appears_verbatim("H2SO4", "UN 1830; H2SO4; OHS22350")
        assert not ms.appears_verbatim("H2SO4", "분자식: H2-S-O4")


class TestNothingIsGenerated:
    """BR-99 (revised) - a name the document does not print is a string we made."""

    def test_a_name_joined_across_a_line_break_is_rejected(self):
        # doc 727 (대정화금): "...cyclohexylester,Cyclohexyl\nmethacrylate,Methacrylicacid,..."
        out = dict(ms.split_value("Cyclohexyl\nmethacrylate,Methacrylicacid"))
        assert out["Cyclohexylmethacrylate"] == ms.JOINED
        assert out["Methacrylicacid"] is None

    def test_a_joined_name_is_rejected_even_when_printed_elsewhere(self):
        """doc 727 prints `Cyclohexylmethacrylate` in 화학물질명, not in the list it came from."""
        text = (
            "화학물질명 Cyclohexylmethacrylate\n"
            "관용명및이명 Cyclohexyl\nmethacrylate,Methacrylicacid\n"
            "CAS번호또는식별번호 101-43-9"
        )
        document = ms.MsdsDocument(
            DOC, None, 35, "101-43-9", text, ((text, ms.COMPOSITION_SECTION),)
        )
        verdicts = {c.term: c.reason for c in ms.extract(document)[0]}
        assert verdicts["Cyclohexylmethacrylate"] == ms.JOINED
        assert verdicts["Methacrylicacid"] is None

    def test_a_name_missing_from_the_extracted_text_is_rejected(self):
        """The gate over every type, in the extracted text the offsets point into."""
        chunk = "관용명및이명 Tetraethoxysilane\nCAS번호 78-10-4"
        extracted = "관용명및이명 Tetraethoxy silane\nCAS번호 78-10-4"
        document = ms.MsdsDocument(
            DOC, None, 16, "78-10-4", extracted, ((chunk, ms.COMPOSITION_SECTION),)
        )
        verdicts = {c.term: c.reason for c in ms.extract(document)[0]}
        assert verdicts["Tetraethoxysilane"] == ms.NOT_PRINTED

    def test_the_gate_is_case_sensitive(self):
        assert ms.printed_in("Tetraethoxysilane", "관용명 Tetraethoxysilane")
        assert not ms.printed_in("TETRAETHOXYSILANE", "관용명 Tetraethoxysilane")


def _doc(document_id, substance_id, cas, names):
    text = f"관용명및이명 {names}\nCAS번호 {cas}"
    return ms.MsdsDocument(
        document_id, None, substance_id, cas, text, ((text, ms.COMPOSITION_SECTION),)
    )


class TestJudgedAgainstTheCorpus:
    def test_a_document_returns_only_its_own_candidates(self):
        current = _doc(728, 16, "78-10-4", "Tetraethoxysilane")
        other = _doc(730, 1, "75-31-0", "2-Propanamine")
        result = ms.names_for(current, [other], {16: ["에틸 실리케이트"], 1: ["아이소프로필아민"]})
        assert {(c.document_id, c.term, c.reason) for c in result} == {
            (728, "Tetraethoxysilane", None)
        }

    def test_another_documents_claim_makes_a_name_ambiguous(self):
        """The same verdict whichever of the two is being indexed."""
        first = _doc(723, 41, "79-10-7", "Propenoicacid")
        second = _doc(727, 35, "101-43-9", "2-Methyl-2-propenoicacid")
        base = {41: ["아크릴산"], 35: ["사이클로헥실 메타크릴레이트"]}
        verdict = {c.term: c.reason for c in ms.names_for(first, [second], base)}
        assert verdict["Propenoicacid"].startswith("모호")
        verdict = {c.term: c.reason for c in ms.names_for(second, [first], base)}
        assert verdict["2-Methyl-2-propenoicacid"] is None


class TestRegister:
    class Repo:
        def __init__(self):
            self.calls = []

        def get_by_id(self, substance_id):
            return f"substance-{substance_id}"

        def replace_document_synonyms(self, document_id, entries, *, owned_types):
            self.calls.append((document_id, entries, frozenset(owned_types)))
            return sum(len(terms) for _s, terms in entries)

    def test_a_document_writes_its_accepted_names_under_its_own_id(self):
        repo = self.Repo()
        current = _doc(728, 16, "78-10-4", "Tetraethoxysilane")
        assert ms.register(repo, 728, current, [], {16: ["에틸 실리케이트"]}) == 1
        assert repo.calls == [
            (
                728,
                [("substance-16", [("Tetraethoxysilane", "tetraethoxysilane",
                                    SynonymType.COMMON_NAME)])],
                ms.MSDS_SYNONYM_TYPES,
            )
        ]

    def test_a_document_that_is_no_single_subject_msds_clears_its_rows(self):
        repo = self.Repo()
        assert ms.register(repo, 38, None, [], {}) == 0
        assert repo.calls == [(38, [], ms.MSDS_SYNONYM_TYPES)]


def test_every_msds_type_is_readable_by_the_lookup():
    """`SubstanceLookup._by_name` runs `SynonymType(row.term_type)` on every hit."""
    from app.substances.lookup import _SYNONYM_KIND

    for term_type in ms.MSDS_TYPES:
        assert _SYNONYM_KIND[SynonymType(term_type)] is MatchKind.ALIAS
