"""Normalisation and token counting — BR-14, BR-27, BR-31.

Normalisation output *is* the offset basis for every citation (FQ-5=A), so these
rules are effectively part of the storage format.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.processing.stages.normalize import normalize, tabulate
from app.processing.tokens import count_tokens


class TestNormalize:
    def test_control_characters_removed(self):
        assert normalize("A\x00B\x07C") == "ABC"

    def test_tab_and_newline_survive(self):
        assert "\n" in normalize("A\nB")

    def test_crlf_becomes_lf(self):
        assert normalize("A\r\nB") == "A\nB"

    def test_runs_of_spaces_collapse(self):
        assert normalize("A     B") == "A B"

    def test_hyphenated_line_break_is_rejoined(self):
        """A PDF that wraps '안전보건' as '안전-\\n보건' must not index two words."""
        assert normalize("안전-\n보건 자료") == "안전보건 자료"

    def test_unicode_is_composed(self):
        decomposed = "가"  # ㄱ + ㅏ in jamo form
        assert normalize(decomposed) == "가"  # 가

    def test_paragraph_breaks_are_preserved_but_bounded(self):
        assert normalize("A\n\n\n\n\nB") == "A\n\nB"

    def test_trailing_whitespace_before_newline_is_dropped(self):
        assert normalize("A   \nB") == "A\nB"

    def test_empty_input(self):
        assert normalize("") == ""

    def test_idempotent(self, msds_text):
        """Running it twice must not shift a single offset."""
        assert normalize(msds_text) == msds_text


class TestTabulate:
    def test_rows_become_lines(self):
        assert tabulate([["a", "b"], ["c", "d"]]) == "a b\nc d"

    def test_empty_cells_are_dropped(self):
        assert tabulate([["a", "", "b"]]) == "a b"


class TestTokenCount:
    def test_empty_is_zero(self):
        assert count_tokens("") == 0

    def test_korean_costs_more_per_character_than_ascii(self):
        korean = count_tokens("가나다라마바사아자차")
        ascii_text = count_tokens("abcdefghij")
        assert korean > ascii_text

    def test_monotonic_in_length(self):
        assert count_tokens("가나다") <= count_tokens("가나다라마")

    @given(st.text(min_size=1, max_size=500))
    def test_always_positive_for_non_empty(self, text):
        assert count_tokens(text) >= 1

    @given(st.text(max_size=300), st.text(max_size=300))
    def test_concatenation_is_roughly_additive(self, a, b):
        """Not exactly additive because of rounding, but never wildly off -
        chunk sizing depends on this staying sane."""
        combined = count_tokens(a + b)
        parts = count_tokens(a) + count_tokens(b)
        assert combined <= parts + 2
