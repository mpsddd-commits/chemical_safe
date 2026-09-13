"""Backlog D11 - the rules `scripts/backfill_synonyms.py` uses to pick synonyms.

The table is matched by substring (`normalized_term in query`), so a wrong row
resolves a question to the wrong substance. These pin the exclusions that stop
that, and the idempotency that lets the script run twice.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from app.core.types import MatchKind, SynonymType

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "backfill_synonyms.py"
_spec = importlib.util.spec_from_file_location("backfill_synonyms", _PATH)
bs = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = bs  # dataclasses resolves annotations through it
_spec.loader.exec_module(bs)

SULFURIC, MEK, DIMETHYLBUTANONE, TBA = 47, 49, 11, 9
BASE = {
    SULFURIC: ["황산", "Sulfuric acid"],
    MEK: ["메틸 에틸 케톤", "Methyl ethyl ketone"],
    DIMETHYLBUTANONE: ["3,3-다이메틸-2-뷰탄온", "3,3-Dimethyl-2-butanone"],
    TBA: ["3차-뷰틸아민", "tert-Butylamine"],
}


def _verdicts(result):
    return {(c.substance_id, c.term): c.reason for c in result}


def _cand(sid, term, term_type=None, pair=None):
    return bs.Candidate(sid, term, term_type or bs.COMMON_NAME, ["test"], pair=pair)


class TestAmbiguity:
    def test_a_term_inside_another_substances_name_is_excluded(self):
        # "2-Butanone" is printed for MEK, and sits inside 3,3-dimethyl-2-butanone.
        result = bs.screen([_cand(MEK, "2-Butanone")], BASE)
        reason = _verdicts(result)[(MEK, "2-Butanone")]
        assert reason is not None and reason.startswith("모호")

    def test_a_term_two_substances_both_claim_is_excluded_for_both(self):
        result = bs.screen([_cand(SULFURIC, "Oil of vitriol"), _cand(MEK, "Oil of vitriol")], BASE)
        verdicts = _verdicts(result)
        assert verdicts[(SULFURIC, "Oil of vitriol")].startswith("모호")
        assert verdicts[(MEK, "Oil of vitriol")].startswith("모호")

    def test_the_gloss_of_an_ambiguous_name_goes_with_it(self):
        result = bs.screen(
            [_cand(MEK, "2-뷰타논", pair="p"), _cand(MEK, "2-Butanone", pair="p")], BASE
        )
        assert _verdicts(result)[(MEK, "2-뷰타논")] == "모호해서 제외 (짝 표기가 모호)"


class TestShortAndGeneric:
    @pytest.mark.parametrize(
        ("term", "fragment"),
        [("유산", "너무 짧음 (2자)"), ("NH3", "라틴 3자"), ("AIBN", "라틴 4자")],
    )
    def test_short_tokens_are_excluded(self, term, fragment):
        reason = _verdicts(bs.screen([_cand(SULFURIC, term)], BASE))[(SULFURIC, term)]
        assert reason is not None and fragment in reason

    def test_a_five_letter_formula_is_long_enough(self):
        result = bs.screen([_cand(SULFURIC, "H2SO4", bs.FORMULA)], BASE)
        assert _verdicts(result)[(SULFURIC, "H2SO4")] is None

    @pytest.mark.parametrize("term", ["혼합물", "자료없음", "Solution"])
    def test_generic_nouns_are_excluded(self, term):
        reason = _verdicts(bs.screen([_cand(SULFURIC, term)], BASE))[(SULFURIC, term)]
        assert reason == "일반 명사"

    def test_company_names_are_excluded(self):
        result = bs.screen([_cand(SULFURIC, "남해화학 여수")], BASE, companies=["남해화학"])
        assert _verdicts(result)[(SULFURIC, "남해화학 여수")] == "회사명"


class TestExistingNames:
    def test_the_existing_name_is_not_written_again(self):
        result = bs.screen([_cand(SULFURIC, "SULFURIC ACID", bs.MSDS_TITLE)], BASE)
        assert _verdicts(result)[(SULFURIC, "SULFURIC ACID")] == "기존 이름과 같음"

    def test_a_broader_name_inside_the_existing_one_is_excluded(self):
        # Daejung prints "Butylamine" as a synonym of tert-Butylamine.
        reason = _verdicts(bs.screen([_cand(TBA, "Butylamine")], BASE))[(TBA, "Butylamine")]
        assert reason is not None and reason.startswith("기존 이름의 일부")

    def test_a_spacing_variant_the_document_prints_is_kept(self):
        base = {45: ["메틸알코올", "Methanol"]}
        result = bs.screen([_cand(45, "메틸 알코올")], base)
        assert _verdicts(result)[(45, "메틸 알코올")] is None


class TestIdempotency:
    def test_a_second_run_plans_no_inserts(self):
        result = bs.screen([_cand(45, "메탄올"), _cand(45, "메틸알콜")], {45: ["메틸알코올"]})
        existing: set[tuple[int, str]] = {(45, "메틸알코올")}
        first = bs.plan_inserts(result, existing)
        assert [c.term for c in first] == ["메탄올", "메틸알콜"]
        existing |= {(c.substance_id, c.normalized) for c in first}
        assert bs.plan_inserts(result, existing) == []

    def test_one_row_per_name_even_from_two_sources(self):
        result = bs.screen(
            [_cand(45, "메탄올", bs.MSDS_TITLE), _cand(45, "메탄올", bs.COMMON_NAME)],
            {45: ["메틸알코올"]},
        )
        assert len(result) == 1 and result[0].term_type == bs.COMMON_NAME
        assert result[0].evidence == ["test"]


class TestExcludedTerms:
    """A misprint in the source is not a synonym, and a rerun must not bring it back."""

    FORMAMIDE = 4
    BASE = {FORMAMIDE: ["폼아마이드", "Formamide"]}

    def test_the_formamide_misprint_is_excluded_with_its_reason(self):
        result = bs.screen(
            [_cand(self.FORMAMIDE, "Formanfide"), _cand(self.FORMAMIDE, "Methanamide")], self.BASE
        )
        verdicts = _verdicts(result)
        assert verdicts[(self.FORMAMIDE, "Formanfide")] == "원문 오타 (Formamide 의 오기)"
        assert verdicts[(self.FORMAMIDE, "Methanamide")] is None

    def test_a_rerun_after_the_row_was_deleted_plans_no_insert(self):
        """(d) The row is gone from the table, so `existing` no longer holds it."""
        result = bs.screen([_cand(self.FORMAMIDE, "Formanfide")], self.BASE)
        existing = {(self.FORMAMIDE, "폼아마이드"), (self.FORMAMIDE, "formamide")}
        assert bs.plan_inserts(result, existing) == []


class TestExtraction:
    def test_only_the_row_with_this_substances_cas_counts(self):
        text = (
            "관용명및이명 Chlorine\nCAS번호 7782-50-5\n"
            "관용명및이명 물, 산화이수소\nCAS번호 7732-18-5\n"
        )
        rows = bs.labeled_values(text, "7782-50-5")
        assert rows[0][:2] == ("Chlorine", None)
        assert rows[1][1] == "다른 성분의 행 (CAS 7732-18-5)"

    def test_an_inverted_index_name_is_not_split_into_two_names(self):
        # HEXANEDIOIC ACID is adipic acid - a different substance.
        out = dict(bs.split_value("HEXANEDIOIC ACID, BIS(2-ETHYLHEXYL)ESTER"))
        assert out["HEXANEDIOIC ACID"] is not None
        assert out["BIS(2-ETHYLHEXYL)ESTER"] is not None

    def test_locant_commas_do_not_split(self):
        out = dict(bs.split_value("Isopropylamine,2-Propylamine,Propane,2-amino-"))
        assert out["2-Propylamine"] is None
        assert out["Propane"] is not None  # head of "Propane, 2-amino-"

    def test_a_gloss_yields_both_names(self):
        assert bs.split_value("2-뷰타논(2-Butanone)") == [("2-뷰타논", None), ("2-Butanone", None)]

    def test_title_drops_the_company(self):
        assert bs.title_names("메탄올 (Methanol) - Methanex 국문판") == (
            ["메탄올", "Methanol"],
            "Methanex 국문판",
        )

    def test_formula_label_value_loses_its_hyphens(self):
        assert bs.formula_values("분자식: H2-S-O4") == ["H2SO4"]
        assert bs.appears_verbatim("H2SO4", "UN 1830; H2SO4; OHS22350")
        assert not bs.appears_verbatim("H2SO4", "분자식: H2-S-O4")


def test_every_backfill_type_is_readable_by_the_lookup():
    """`SubstanceLookup._by_name` runs `SynonymType(row.term_type)` on every hit."""
    from app.substances.lookup import _SYNONYM_KIND

    for term_type in bs.BACKFILL_TYPES:
        assert _SYNONYM_KIND[SynonymType(term_type)] is MatchKind.ALIAS
