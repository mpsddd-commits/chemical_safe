"""Fusion and document-type spread — BR-68, BR-69."""

from __future__ import annotations

from app.core.types import Candidate, DocType
from app.rag.retrieval.fusion import ensure_doc_type_spread, reciprocal_rank_fusion
from app.rag.types import RetrievalCandidate


def _kw(*ids: int) -> list[Candidate]:
    return [Candidate(chunk_id=i, score=1.0, route="keyword") for i in ids]


def _vec(*ids: int) -> list[Candidate]:
    return [Candidate(chunk_id=i, score=0.9, route="vector") for i in ids]


class TestRRF:
    def test_appearing_in_both_routes_beats_appearing_in_one(self):
        fused = reciprocal_rank_fusion(_kw(1, 2, 3), _vec(3, 4, 5))
        assert fused[0].chunk_id == 3

    def test_scores_need_no_normalisation(self):
        """BR-68 — only ranks are used, so route score scales are irrelevant."""
        wild = [Candidate(chunk_id=1, score=999_999.0, route="keyword")]
        tiny = [Candidate(chunk_id=2, score=0.000_001, route="vector")]
        fused = reciprocal_rank_fusion(wild, tiny)
        assert fused[0].fused_score == fused[1].fused_score

    def test_order_is_reproducible(self):
        """A query that returns different evidence on retry cannot be debugged."""
        a = reciprocal_rank_fusion(_kw(5, 3, 1), _vec(1, 3, 5))
        b = reciprocal_rank_fusion(_kw(5, 3, 1), _vec(1, 3, 5))
        assert [c.chunk_id for c in a] == [c.chunk_id for c in b]

    def test_both_ranks_are_recorded(self):
        fused = reciprocal_rank_fusion(_kw(7), _vec(7))
        assert fused[0].keyword_rank == 1
        assert fused[0].vector_rank == 1


def _c(chunk_id: int, doc_type: DocType, score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id, document_id=chunk_id, doc_type=doc_type, fused_score=score
    )


class TestDocTypeSpread:
    def test_missing_type_is_lifted_into_the_cut(self):
        """BR-69 — law is 69% of the corpus; it can crowd everything else out."""
        candidates = [
            _c(1, DocType.LAW, 0.9),
            _c(2, DocType.LAW, 0.8),
            _c(3, DocType.LAW, 0.7),
            _c(9, DocType.MSDS, 0.2),
        ]
        result = ensure_doc_type_spread(candidates, limit=3)
        assert DocType.MSDS in {c.doc_type for c in result}
        assert len(result) == 3

    def test_absent_type_is_not_invented(self):
        """NFR-8 — a type with no candidate stays absent rather than fabricated."""
        candidates = [_c(1, DocType.LAW, 0.9), _c(2, DocType.LAW, 0.8)]
        result = ensure_doc_type_spread(candidates, limit=2)
        assert {c.doc_type for c in result} == {DocType.LAW}

    def test_already_mixed_results_are_untouched(self):
        candidates = [
            _c(1, DocType.LAW, 0.9),
            _c(2, DocType.MSDS, 0.8),
            _c(3, DocType.INCIDENT, 0.7),
            _c(4, DocType.LAW, 0.1),
        ]
        result = ensure_doc_type_spread(candidates, limit=3)
        assert [c.chunk_id for c in result] == [1, 2, 3]

    def test_lifting_never_evicts_the_only_member_of_a_type(self):
        candidates = [
            _c(1, DocType.LAW, 0.9),
            _c(2, DocType.LAW, 0.8),
            _c(3, DocType.MSDS, 0.7),
            _c(9, DocType.INCIDENT, 0.1),
        ]
        result = ensure_doc_type_spread(candidates, limit=3)
        types = {c.doc_type for c in result}
        assert DocType.MSDS in types
        assert DocType.INCIDENT in types

    def test_empty_input(self):
        assert ensure_doc_type_spread([], limit=5) == []
