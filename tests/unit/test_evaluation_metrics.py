"""C45·C46 — the metrics that decide whether quality moved.

These are pure functions and the tests are DB-free (NFR-28), which is the point:
they are the half of u4 that can run every day for nothing, so nothing in them
may need a database, a network, or a model.

The cases are drawn from what the real corpus actually does — a golden question
whose evidence has no section (BR-113, thirteen such documents), a citation that
lands on the right document but the wrong section, and a refusal that must not
be scored by its reason.
"""

from __future__ import annotations

import pytest

from app.evaluation import answer_metrics as am
from app.evaluation import retrieval_metrics as rm
from app.evaluation.types import EvidenceRef, RetrievedRef

LAW = EvidenceRef(source="law_api", external_id="000162", section="제13조")
INCIDENT = EvidenceRef(source="incident_data", external_id="2025-155")
RESOLVE = {("law_api", "000162"): 29, ("incident_data", "2025-155"): 6}


def _ref(rank: int, document_id: int, section: str | None, chunk_id: int | None = None):
    return RetrievedRef(
        rank=rank,
        chunk_id=chunk_id if chunk_id is not None else 1000 + rank,
        document_id=document_id,
        section_code=section,
    )


class TestMatching:
    def test_document_and_section_must_both_match(self):
        assert rm.matches(LAW, _ref(0, 29, "제13조"), 29)
        assert not rm.matches(LAW, _ref(0, 29, "제43조"), 29)
        assert not rm.matches(LAW, _ref(0, 30, "제13조"), 29)

    def test_a_sectionless_reference_matches_any_chunk_of_its_document(self):
        """BR-113 — the incident documents have no sections at all.

        BR-31a folded them into one chunk each. Scoring them by section would
        score all twelve as permanently missed, which says something about the
        chunker and nothing about retrieval.
        """
        assert rm.matches(INCIDENT, _ref(0, 6, None), 6)
        assert rm.matches(INCIDENT, _ref(0, 6, "anything"), 6)
        assert not rm.matches(INCIDENT, _ref(0, 7, None), 6)


class TestRecallAndMRR:
    def test_hit_at_rank_zero(self):
        score = rm.score([LAW], [_ref(0, 29, "제13조"), _ref(1, 30, "제10조")], RESOLVE)
        assert score.recall == {5: 1.0, 10: 1.0}
        assert score.reciprocal_rank == 1.0

    def test_recall_at_5_and_10_can_disagree(self):
        """The diagnostic this pair exists for: found, but ranked too low."""
        candidates = [_ref(i, 99, "x") for i in range(7)] + [_ref(7, 29, "제13조")]
        score = rm.score([LAW], candidates, RESOLVE)
        assert score.recall[5] == 0.0
        assert score.recall[10] == 1.0
        assert score.reciprocal_rank == pytest.approx(0.125, abs=0.001)

    def test_miss_scores_zero_not_none(self):
        score = rm.score([LAW], [_ref(0, 99, "제1조")], RESOLVE)
        assert score.recall == {5: 0.0, 10: 0.0}
        assert score.reciprocal_rank == 0.0

    def test_partial_recall_over_several_evidence_refs(self):
        score = rm.score(
            [LAW, INCIDENT], [_ref(0, 29, "제13조"), _ref(1, 99, None)], RESOLVE
        )
        assert score.recall[5] == 0.5
        assert score.expected == 2

    def test_a_refusal_question_is_not_penalised(self):
        """No expected evidence means nothing to find — 1.0, not 0.0.

        Scoring it 0 would drag the corpus-wide Recall down by the share of
        refusal questions, which measures the golden set's composition rather
        than the system.
        """
        score = rm.score([], [_ref(0, 29, "제13조")], RESOLVE)
        assert score.recall == {5: 1.0, 10: 1.0}
        assert score.reciprocal_rank == 1.0
        assert score.expected == 0

    def test_no_candidates_at_all(self):
        score = rm.score([LAW], [], RESOLVE)
        assert score.recall[5] == 0.0
        assert score.reciprocal_rank == 0.0

    def test_rank_order_is_taken_from_rank_not_list_position(self):
        out_of_order = [_ref(3, 99, "x"), _ref(0, 29, "제13조")]
        assert rm.score([LAW], out_of_order, RESOLVE).reciprocal_rank == 1.0


class TestCitationPrecision:
    def test_all_citations_inside_the_expected_evidence(self):
        cited = [_ref(0, 29, "제13조"), _ref(1, 29, "제13조")]
        assert am.citation_precision([LAW], cited, RESOLVE) == 1.0

    def test_right_document_wrong_section_is_wrong(self):
        cited = [_ref(0, 29, "제13조"), _ref(1, 29, "제43조")]
        assert am.citation_precision([LAW], cited, RESOLVE) == 0.5

    def test_no_citations_is_none_not_zero(self):
        """An answer that cited nothing is a different failure from one that
        cited badly, and averaging a 0.0 in would hide which happened."""
        assert am.citation_precision([LAW], [], RESOLVE) is None

    def test_unresolvable_evidence_yields_none(self):
        assert am.citation_precision([LAW], [_ref(0, 29, "제13조")], {}) is None


class TestRefusalScoring:
    @pytest.mark.parametrize(
        "outcome",
        ["refused_low_relevance", "refused_unsupported", "refused_provider"],
    )
    def test_every_refusal_family_counts_as_a_refusal(self, outcome):
        """BR-127 — the family, not the reason.

        Scoring the reason would break the golden set every time the refusal
        taxonomy is refined, and FR-37 asks a simpler question.
        """
        assert am.is_refusal(outcome)

    @pytest.mark.parametrize("outcome", ["answered", "answered_partial", None, ""])
    def test_non_refusals(self, outcome):
        assert not am.is_refusal(outcome)

    def test_correctness_depends_on_what_was_expected(self):
        assert am.refusal_correct(True, "refused_low_relevance")
        assert not am.refusal_correct(True, "answered")
        assert am.refusal_correct(False, "answered")
        assert not am.refusal_correct(False, "refused_low_relevance")

    def test_accuracy_and_false_refusal_are_reported_together(self):
        """BR-128 — accuracy alone gives a system that refuses everything 1.0."""
        items = [
            (True, "refused_low_relevance"),
            (True, "refused_low_relevance"),
            (False, "answered"),
            (False, "refused_low_relevance"),
        ]
        rates = am.refusal_rates(items)
        assert rates["accuracy"] == 1.0
        assert rates["false_refusal"] == 0.5

    def test_a_system_that_refuses_everything_is_visibly_bad(self):
        items = [(True, "refused_low_relevance"), (False, "refused_low_relevance")]
        rates = am.refusal_rates(items)
        assert rates["accuracy"] == 1.0
        assert rates["false_refusal"] == 1.0

    def test_missing_side_is_none(self):
        rates = am.refusal_rates([(True, "refused_low_relevance")])
        assert rates["accuracy"] == 1.0
        assert rates["false_refusal"] is None
