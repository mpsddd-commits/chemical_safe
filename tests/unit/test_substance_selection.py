"""BR-08 substance selection — defect 44.

The master held the first 40 records the API returned and the MSDS corpus
documents eight substances, and the two sets did not intersect at all. Every
card came back six items out of seven empty. These tests pin the two decisions
that fix it: which names are pulled out of the corpus, and that a name has to
match **exactly** to earn a slot.

The inputs are the real ones. Every accident record in the corpus appears
verbatim below, because the awkward cases here (a mixture in parentheses, a
prime written with a different code point) are not hypotheticals — they are
what the two sources actually contain.
"""

from __future__ import annotations

import pytest

from app.ingestion.substance_selection import candidate_terms, normalise, partition

# The 12 accident records, exactly as `incident_substance` stores them.
INCIDENT_SECTIONS = [
    "substances: 폐산(지정폐기물)",
    "substances: 인쇄용 잉크제품: PET-MD107(톨루엔 30~35 %, 메틸에틸케톤 35~40 %,"
    " PVC 폴리머 15~20 %, 2-메톡시프로판올 5~10%)",
    "substances: 염소",
    "substances: 암모니아(100%)",
    "substances: 수소",
    "substances: 4,4‛-디이소시안산 디페닐메탄(MDI)(25~30%)",
    "substances: N,N-디메틸포름아미드(100%)",
    "substances: 사염화티타늄(99.5%)",
    "substances: 아크릴산(1~3%)",
    "substances: 암모니아(100%)",
    "substances: 4,4‛-디이소시안산디페닐메탄(MDI)",
    "substances: 암모니아",
]

# The 8 MSDS PDF titles.
MSDS_TITLES = [
    "황산 (SULFURIC ACID) - 남해화학",
    "황산 - 코리아케미칼",
    "염산 (Hydrochloric acid) - 덕산약품",
    "톨루엔 - SK케미칼",
    "톨루엔 (Toluene) - 한화토탈",
    "메탄올 (Methanol) - Methanex 국문판",
    "선형저밀도폴리에틸렌 R905U - 한화토탈",
    "하이큐 프라서페 PS-220 PLUS (혼합물)",
]


class TestNormalise:
    def test_list_marker_is_stripped(self):
        """Every Korean name in the master is rendered "·톨루엔"."""
        assert normalise("·톨루엔") == normalise("톨루엔")

    def test_hyphen_is_not_stripped(self):
        """It is part of the name in "2-메톡시프로판올"."""
        assert normalise("-톨루엔") != normalise("톨루엔")

    def test_apostrophe_variants_fold_together(self):
        """The accident record writes ‛ and the master writes ’."""
        record, master = "4,4‛-디이소시안산 디페닐메탄", "4,4’-디이소시안산 디페닐메탄"
        assert normalise(record) == normalise(master)

    def test_whitespace_is_removed_not_collapsed(self):
        """The master says "메틸 에틸 케톤", the accident record "메틸에틸케톤"."""
        assert normalise("메틸 에틸 케톤") == normalise("메틸에틸케톤")

    def test_case_is_folded(self):
        assert normalise("SULFURIC ACID") == normalise("Sulfuric Acid")

    def test_empty_input_is_safe(self):
        assert normalise(None) == ""


class TestCandidateTerms:
    def _terms(self):
        return candidate_terms(INCIDENT_SECTIONS + MSDS_TITLES)

    def test_label_is_not_a_term(self):
        assert "substances" not in {t.casefold() for t in self._terms()}

    def test_mixture_components_survive_their_concentrations(self):
        """The whole point of the mixture case: 톨루엔 is inside the parentheses.

        Stripping parenthesised text — which is what removing a concentration
        naively looks like — throws away the only substance in that record that
        the corpus has an MSDS for.
        """
        terms = self._terms()
        assert "톨루엔" in terms
        assert "메틸에틸케톤" in terms
        assert "2-메톡시프로판올" in terms

    def test_comma_inside_a_name_is_not_a_separator(self):
        """Splitting on it produced "4‛-디이소시안산 디페닐메탄", which matches nothing."""
        terms = self._terms()
        assert "4,4‛-디이소시안산 디페닐메탄" in terms
        assert "N,N-디메틸포름아미드" in terms

    def test_vendor_tail_is_dropped_from_a_title(self):
        terms = self._terms()
        assert "황산" in terms
        assert not any("남해화학" in t for t in terms)

    def test_english_name_from_a_title_is_offered(self):
        """메탄올 is not in the master; "Methanol" finds 메틸알코올."""
        assert "Methanol" in self._terms()

    def test_product_head_is_offered(self):
        assert "선형저밀도폴리에틸렌" in self._terms()

    def test_terms_are_deduplicated(self):
        terms = self._terms()
        assert len(terms) == len(set(terms))

    def test_single_characters_are_dropped(self):
        assert candidate_terms(["substances: A(1%)"]) == []

    def test_empty_input_is_not_an_error(self):
        assert candidate_terms([]) == []
        assert candidate_terms(["", "   ", "substances:"]) == []


class TestPartition:
    ROWS = [
        ("iso", ("·아이소프로필아민", "Isopropylamine")),
        ("bromotoluene", ("·2-브로모톨루엔", "2-Bromotoluene")),
        ("toluene", ("·톨루엔", "Toluene")),
        ("copper-sulfate", ("·황산구리", "Copper sulfate")),
        ("sulfuric", ("·황산", "Sulfuric acid")),
        ("mek", ("·메틸 에틸 케톤", "Methyl ethyl ketone")),
    ]

    def test_matched_rows_come_first(self):
        selected, matched = partition(self.ROWS, ["톨루엔", "황산"], target=6)
        assert selected[:2] == ["toluene", "sulfuric"]
        assert matched == 2

    def test_substring_does_not_match(self):
        """Measured: "톨루엔" is a substring of 68 master entries and "황산" of 56.

        A 40-record budget filled with derivatives would leave the substance the
        user actually asked about outside the master — the defect this replaces,
        arrived at by a different route.
        """
        selected, matched = partition(self.ROWS, ["톨루엔", "황산"], target=6)
        assert "bromotoluene" not in selected[:2]
        assert "copper-sulfate" not in selected[:2]
        assert matched == 2

    def test_english_name_can_be_the_match(self):
        _selected, matched = partition(self.ROWS, ["Methyl ethyl ketone"], target=6)
        assert matched == 1

    def test_unmatched_rows_keep_source_order(self):
        """The remainder is exactly the previous behaviour."""
        selected, _matched = partition(self.ROWS, ["톨루엔"], target=6)
        assert selected[1:] == ["iso", "bromotoluene", "copper-sulfate", "sulfuric", "mek"]

    def test_target_cuts_after_ranking_not_before(self):
        selected, matched = partition(self.ROWS, ["메틸에틸케톤"], target=1)
        assert selected == ["mek"]
        assert matched == 1

    def test_no_terms_leaves_the_order_alone(self):
        selected, matched = partition(self.ROWS, [], target=3)
        assert selected == ["iso", "bromotoluene", "toluene"]
        assert matched == 0

    def test_more_matches_than_target_still_cuts(self):
        selected, matched = partition(self.ROWS, ["톨루엔", "황산", "메틸에틸케톤"], target=2)
        assert len(selected) == 2
        assert matched == 3

    @pytest.mark.parametrize("target", [0, 1, 100])
    def test_target_bounds(self, target):
        selected, _matched = partition(self.ROWS, ["톨루엔"], target=target)
        assert len(selected) == min(target, len(self.ROWS))


class TestEndToEndAgainstTheRealCorpus:
    """What the corpus terms actually find in the master.

    Measured against a full 7,189-row scan on 2026-08-27. Eight distinct
    substances match, and these are the ones that turn an empty card into a
    populated one.
    """

    MASTER = {
        "·톨루엔": "108-88-3",
        "·메틸 에틸 케톤": "78-93-3",
        "·염소": "7782-50-5",
        "·암모니아": "7664-41-7",
        "·수소": "1333-74-0",
        "·아크릴산": "79-10-7",
        "·황산": "7664-93-9",
        "·메틸알코올": "67-56-1",
        "·아이소프로필아민": "75-31-0",
    }
    # Named in the corpus, absent from the master under that name. Recorded
    # rather than asserted away: the gap is a fact about the source.
    ABSENT = ["폐산", "사염화티타늄", "N,N-디메틸포름아미드", "2-메톡시프로판올", "염산"]

    def _rows(self):
        english = {"·메틸알코올": "Methanol", "·황산": "Sulfuric acid", "·톨루엔": "Toluene"}
        return [(name, (name, english.get(name, ""))) for name in self.MASTER]

    def test_the_measured_eight_are_selected(self):
        terms = candidate_terms(INCIDENT_SECTIONS + MSDS_TITLES)
        selected, matched = partition(self._rows(), terms, target=40)
        assert matched == 8
        assert set(selected[:8]) == set(self.MASTER) - {"·아이소프로필아민"}

    def test_names_the_master_does_not_carry_match_nothing(self):
        selected, matched = partition(self._rows(), self.ABSENT, target=40)
        assert matched == 0
        assert selected[0] == "·톨루엔"  # untouched source order
