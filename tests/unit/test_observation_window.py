"""C4(b) — the observation window must widen the view, never move the head.

Recall@5 is read off the first five positions of the same list Recall@10 is
read off. That is what makes this cheap, and it is also what makes it easy to
break: the obvious way to get a ten-deep list is to raise `FINAL_TOP_K`, and
that rebuilds the head through `ensure_doc_type_spread`. Measured 2026-09-06
(runs 550 and 551): Recall@5 fell 0.967 → 0.933, sub-02 gained, sub-06 and
sub-07 lost. So every test here is a guard on "the head did not move".

No database, no network, no model (NFR-28) — `observation_window` is pure.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.types import DocType
from app.rag.types import RetrievalCandidate
from app.services.query_service import observation_window


def _candidate(chunk_id: int, score: float = 0.0) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        document_id=chunk_id * 10,
        doc_type=DocType.MSDS,
        fused_score=score or 1.0 / chunk_id,
    )


def _fused(*chunk_ids: int) -> list[RetrievalCandidate]:
    return [_candidate(cid) for cid in chunk_ids]


class TestTheHeadIsNotNegotiable:
    def test_the_first_positions_are_the_head_in_order(self):
        """The Recall@5 guard, stated as an assertion."""
        head = _fused(7, 3, 9, 1, 5)
        window = observation_window(head, _fused(1, 2, 3, 4, 5, 6, 7, 8, 9), depth=10)

        assert [c.chunk_id for c in window[:5]] == [7, 3, 9, 1, 5]

    def test_the_head_is_not_reordered_into_fused_order(self):
        """`ensure_doc_type_spread` and BR-65a both promote out of fused order.

        Sorting the window would undo that promotion, which is exactly the
        failure raising FINAL_TOP_K produced.
        """
        head = _fused(9, 1)
        window = observation_window(head, _fused(1, 2, 3, 9), depth=4)

        assert [c.chunk_id for c in window] == [9, 1, 2, 3]

    def test_a_depth_below_the_head_truncates_nothing(self):
        head = _fused(1, 2, 3, 4, 5)
        window = observation_window(head, _fused(1, 2, 3, 4, 5, 6, 7), depth=2)

        assert [c.chunk_id for c in window] == [1, 2, 3, 4, 5]


class TestTheTail:
    def test_it_stops_at_the_observation_depth(self):
        window = observation_window(_fused(1), _fused(*range(1, 21)), depth=10)

        assert len(window) == 10

    def test_it_skips_what_the_head_already_lifted(self):
        """A chunk counted twice would be counted twice by Recall@10."""
        head = _fused(4, 17)
        window = observation_window(head, _fused(1, 2, 3, 4, 5, 17, 6), depth=10)

        ids = [c.chunk_id for c in window]
        assert ids == [4, 17, 1, 2, 3, 5, 6]
        assert len(ids) == len(set(ids))

    def test_a_short_fused_list_yields_a_short_window(self):
        """Fewer than ten candidates is a fact, not a shortfall to pad."""
        head = _fused(1, 2)
        window = observation_window(head, _fused(1, 2, 3), depth=10)

        assert [c.chunk_id for c in window] == [1, 2, 3]

    def test_an_empty_fused_list_yields_the_head_alone(self):
        head = _fused(1, 2)
        assert [c.chunk_id for c in observation_window(head, [], depth=10)] == [1, 2]


class TestTheDepthSetting:
    def test_the_default_is_ten_and_fits_inside_fusion(self):
        settings = Settings(postgres_password="x")

        assert settings.observation_top_k == 10
        assert settings.observation_top_k <= settings.fusion_top_k

    def test_it_cannot_ask_for_more_than_fusion_produced(self):
        """Past `fusion_top_k` there is nothing ranked to observe."""
        with pytest.raises(ValueError, match="OBSERVATION_TOP_K"):
            Settings(postgres_password="x", fusion_top_k=20, observation_top_k=21)

    def test_zero_is_rejected(self):
        with pytest.raises(ValueError, match="OBSERVATION_TOP_K"):
            Settings(postgres_password="x", observation_top_k=0)
