"""Two-column PDF rescue - the pure parts (2026-09-01).

The geometry detector over-triggers on tables (measured: autorefinishes-ps220
went 0 -> 2 header inversions when column mode ran unconditionally), which is
why the runner gates adoption on structuring success. These tests pin the
reassembly arithmetic; the two real documents are covered by the integration
suite against the live corpus.
"""

from __future__ import annotations

from app.processing.stages.extract import _reassemble_lines


class TestLineReassembly:
    def test_rows_read_top_to_bottom(self):
        """PDF y grows upward, reading order goes downward."""
        frags = [(10.0, 100.0, "아래"), (10.0, 700.0, "위")]
        assert _reassemble_lines(frags) == ["위", "아래"]

    def test_a_row_reads_left_to_right(self):
        frags = [(300.0, 500.0, "오른쪽"), (10.0, 500.0, "왼쪽")]
        assert _reassemble_lines(frags) == ["왼쪽 오른쪽"]

    def test_nearby_y_values_share_a_row(self):
        """Fragments of one visual line rarely share an exact baseline."""
        frags = [(10.0, 500.2, "같은"), (60.0, 500.4, "줄")]
        assert _reassemble_lines(frags) == ["같은 줄"]

    def test_each_line_is_its_own_string(self):
        """`^`-anchored header patterns die if lines are glued together -
        the first prototype produced one line per page and matched nothing."""
        frags = [(10.0, 700.0, "1. 화학제품과 회사에 관한 정보"), (10.0, 650.0, "2. 유해성·위험성")]
        lines = _reassemble_lines(frags)
        assert len(lines) == 2
