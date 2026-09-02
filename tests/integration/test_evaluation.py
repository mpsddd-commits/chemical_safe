"""u4 against a live PostgreSQL and the real corpus.

The unit tests cover the arithmetic; what needs a database is whether the golden
set actually points at documents that exist, and whether a `--retrieval-only`
run really touches no model. Both are the kind of thing a mock cannot answer —
the same lesson u2 recorded when defects 26, 31, 37, 38 and 43 all passed their
unit tests.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.build import build_id
from app.core.errors import ConfigurationError
from app.db.engine import session_scope
from app.db.models import EvaluationItem, EvaluationRun
from app.db.repositories.evaluation import EvaluationRepo
from app.evaluation.golden_set import GoldenSetLoader
from app.evaluation.types import ItemOutcome, ItemStatus, RunMode, RunStatus
from app.services.evaluation_service import EvaluationService

pytestmark = pytest.mark.integration

GOLDEN = Path(__file__).resolve().parents[2] / "eval" / "golden-set.yaml"


TEST_NOTE = "integration-test"


def _mark(summary):
    """Label runs these tests create.

    They land in the same `evaluation_run` history a person reads with
    `evaluate --list`, and a history where most rows came from a test suite is
    hard to read. Labelling does not remove them; it makes them prunable on
    purpose rather than invisible.
    """
    with session_scope() as session:
        run = EvaluationRepo(session).get_run(summary.run_id)
        if run is not None:
            run.note = TEST_NOTE
            session.flush()
    return summary


@contextmanager
def _baseline_restored():
    """Put the promoted baseline back the way the test found it.

    A test that promotes a baseline changes what the *next real run* compares
    against - measured, run 10 came out `incomparable` against a retrieval-only
    run these tests had left promoted. Milder than defect 48 but the same shape:
    a test quietly changing the state it shares with the system it is testing.
    """
    with session_scope() as session:
        previous = [
            run.id
            for run in session.scalars(
                select(EvaluationRun).where(EvaluationRun.is_baseline.is_(True))
            )
        ]
    try:
        yield
    finally:
        with session_scope() as session:
            repo = EvaluationRepo(session)
            for run in session.scalars(
                select(EvaluationRun).where(EvaluationRun.is_baseline.is_(True))
            ):
                run.is_baseline = False
            session.flush()
            for run_id in previous:
                restored = repo.get_run(run_id)
                if restored is not None:
                    restored.is_baseline = True
            session.flush()


class TestGoldenSetResolvesAgainstTheCorpus:
    """BR-114 — this is the check that makes a week-long run safe to start."""

    def test_every_reference_exists(self):
        with session_scope() as session:
            golden = GoldenSetLoader(session).load(GOLDEN)
        assert len(golden) == 30

    def test_sectionless_references_are_the_incident_documents(self):
        """BR-113 — and there is no other kind in the set."""
        with session_scope() as session:
            golden = GoldenSetLoader(session).load(GOLDEN)
        sectionless = [
            (q.id, ref.source)
            for q in golden.questions
            for ref in q.evidence
            if ref.section is None
        ]
        assert sectionless
        assert {source for _qid, source in sectionless} == {"incident_data"}

    def test_the_corpus_is_the_one_the_set_was_written_against(self):
        """A renamed section code after a parsing change breaks this first."""
        with session_scope() as session:
            # Raises with every failing reference listed, not just the first.
            GoldenSetLoader(session).load(GOLDEN)


class TestRetrievalOnlyRun:
    """BR-119 — the daily loop. Zero LLM calls, whole set, seconds."""

    @pytest.fixture(scope="class")
    def summary(self):
        return _mark(
            EvaluationService().run(
                mode=RunMode.RETRIEVAL_ONLY, golden_set_path=str(GOLDEN)
            )
        )

    def test_every_question_is_scored(self, summary):
        assert summary.status is RunStatus.SUCCEEDED
        assert summary.metrics["counts"]["done"] == 30
        assert summary.metrics["counts"]["failed"] == 0

    def test_no_llm_call_was_made(self, summary):
        """`_NoLLM` raises rather than calling; a failure here would surface as
        a failed item, so this assertion is real."""
        assert summary.metrics["cost"]["llm_calls"] == 0
        with session_scope() as session:
            run = EvaluationRepo(session).get_run(summary.run_id)
            assert run.llm_calls == 0
            assert run.answer_model is None
            assert run.judge_model is None

    def test_retrieval_metrics_are_present_and_answer_metrics_are_not(self, summary):
        assert summary.metrics["retrieval"]["recall_at_5"] is not None
        assert summary.metrics["retrieval"]["mrr"] is not None
        assert "answer" not in summary.metrics
        assert "judge" not in summary.metrics

    def test_refusal_accuracy_is_measured(self, summary):
        assert summary.metrics["refusal"]["accuracy"] is not None
        assert summary.metrics["refusal"]["false_refusal"] is not None

    def test_the_candidate_list_is_stored_for_reuse(self, summary):
        """BR-121 — changing k must not cost a day of quota."""
        with session_scope() as session:
            rows = EvaluationRepo(session).items(summary.run_id)
        assert any(row.retrieved for row in rows)
        first = next(row for row in rows if row.retrieved)
        assert {"rank", "chunk_id", "document_id", "section_code"} <= set(
            first.retrieved[0]
        )

    def test_the_run_records_what_it_measured(self, summary):
        """Without this a moved number cannot be attributed to anything."""
        with session_scope() as session:
            run = EvaluationRepo(session).get_run(summary.run_id)
        assert run.corpus_fingerprint["chunks"] > 0
        assert run.config["final_top_k"]
        assert run.golden_set_hash


class TestResumeAndBaseline:
    def _run(self):
        return _mark(
            EvaluationService().run(
                mode=RunMode.RETRIEVAL_ONLY, golden_set_path=str(GOLDEN)
            )
        )

    def test_a_succeeded_run_cannot_be_resumed(self):
        summary = self._run()
        with pytest.raises(Exception, match="partial"):
            EvaluationService().resume(summary.run_id)

    def test_resume_skips_what_was_already_scored(self):
        """BR-117 — one question, one transaction, and never scored twice."""
        summary = self._run()
        with session_scope() as session:
            repo = EvaluationRepo(session)
            scored = repo.scored_question_ids(summary.run_id)
        assert len(scored) == 30

    def test_promotion_is_explicit_and_exclusive_within_a_mode(self):
        """BR-129 — one baseline per mode, and promoting replaces it.

        Per mode rather than overall: a retrieval-only baseline and a full
        baseline describe different amounts of pipeline, and both are wanted
        (defect 55).
        """
        with _baseline_restored():
            first = self._run()
            second = self._run()
            service = EvaluationService()
            service.promote_baseline(first.run_id)
            service.promote_baseline(second.run_id)
            with session_scope() as session:
                count = session.scalar(
                    select(func.count())
                    .select_from(EvaluationRun)
                    .where(
                        EvaluationRun.is_baseline.is_(True),
                        EvaluationRun.mode == "retrieval_only",
                    )
                )
                baseline = EvaluationRepo(session).latest_baseline("retrieval_only")
            assert count == 1
            assert baseline.id == second.run_id

    def test_each_mode_keeps_its_own_baseline(self):
        """Defect 55 - one baseline overall made the daily guard useless.

        A retrieval-only run has no answer model, no judge model and no prompt
        versions, so against a `full` baseline it differs on three fields and
        comes back `incomparable` every time. Measured on run 48: identical
        Recall and MRR, and a 거부 정확도 "drop" of 0.200 that was only the
        absence of stage-two verification. The regression guard the two-tier
        split exists to provide would never have fired once.
        """
        with _baseline_restored():
            retrieval = self._run()
            service = EvaluationService()
            service.promote_baseline(retrieval.run_id)

            full_id = self._run().run_id
            with session_scope() as session:
                repo = EvaluationRepo(session)
                # Stand in for a promoted full run without spending quota.
                full = repo.get_run(full_id)
                full.mode = "full"
                repo.set_baseline(full, True)

            with session_scope() as session:
                repo = EvaluationRepo(session)
                # Promoting the full run must not have unseated the other mode's.
                assert repo.latest_baseline("retrieval_only").id == retrieval.run_id
                assert repo.latest_baseline("full").id == full_id

    def test_a_retrieval_only_baseline_cannot_grade_a_full_run(self):
        """Measured on run 10: `incomparable`, and rightly so.

        A retrieval-only run records no answer model, no judge model and no
        prompt versions, so a full run compared against it differs on three
        fields at once. The deltas are still shown - that is how you see what
        moved - but no regression is declared from two runs that measured
        different amounts.
        """
        from app.evaluation.types import Verdict

        baseline_run = self._run()
        candidate = self._run()
        service = EvaluationService()
        with session_scope() as session:
            repo = EvaluationRepo(session)
            # Stand in for a full run without spending a day of quota.
            run = repo.get_run(candidate.run_id)
            run.mode = "full"
            run.answer_model = "gemini-3.1-flash-lite"
            run.judge_model = "gemini-3.6-flash"
            run.prompt_versions = {"answer": "1.0.0", "verify": "1.0.0", "judge": "1.0.0"}
            session.flush()

        report = service.compare(candidate.run_id, baseline_id=baseline_run.run_id)
        assert report.verdict is Verdict.INCOMPARABLE
        assert any("answer_model" in w for w in report.warnings)
        assert report.deltas  # still shown

    def test_comparing_a_run_with_itself_is_not_a_comparison(self):
        with _baseline_restored():
            summary = self._run()
            service = EvaluationService()
            service.promote_baseline(summary.run_id)
            report = service.compare(summary.run_id)
            assert report.baseline_id is None


class TestItemPersistence:
    def test_recording_the_same_question_twice_updates_one_row(self):
        """The unique constraint is what makes a resume safe."""
        from app.evaluation.types import Expects

        with session_scope() as session:
            run = EvaluationRepo(session).create_run(
                mode=RunMode.RETRIEVAL_ONLY,
                golden_set_path=str(GOLDEN),
                golden_set_hash="x",
                question_count=1,
                config={},
                embedding_model=None,
                answer_model=None,
                judge_model=None,
                prompt_versions={},
                corpus_fingerprint={},
            )
            run.note = TEST_NOTE
            run_id = run.id

        outcome = ItemOutcome(
            question_id="law-01",
            category="law",
            expects=Expects.ANSWER,
            status=ItemStatus.QUOTA_EXHAUSTED,
        )
        with session_scope() as session:
            EvaluationRepo(session).record(run_id, outcome)
        outcome.status = ItemStatus.DONE
        with session_scope() as session:
            EvaluationRepo(session).record(run_id, outcome)

        with session_scope() as session:
            rows = session.scalars(
                select(EvaluationItem).where(EvaluationItem.run_id == run_id)
            ).all()
        assert len(rows) == 1
        assert rows[0].status == "done"

    def test_re_scoring_moves_the_timestamp(self):
        """Defect 54 - a resumed item kept the date of the day it failed.

        `server_default=now()` fires on insert only, so inc-01 was scored on
        08-29 and still claimed 08-28. This unit exists to attribute change over
        time; a timestamp that names the wrong day undermines that directly.
        """
        from app.evaluation.types import Expects

        with session_scope() as session:
            run = EvaluationRepo(session).create_run(
                mode=RunMode.RETRIEVAL_ONLY,
                golden_set_path=str(GOLDEN),
                golden_set_hash="x",
                question_count=1,
                config={},
                embedding_model=None,
                answer_model=None,
                judge_model=None,
                prompt_versions={},
                corpus_fingerprint={},
            )
            run.note = TEST_NOTE
            run_id = run.id

        outcome = ItemOutcome(
            question_id="law-01",
            category="law",
            expects=Expects.ANSWER,
            status=ItemStatus.QUOTA_EXHAUSTED,
        )
        with session_scope() as session:
            first = EvaluationRepo(session).record(run_id, outcome).evaluated_at

        outcome.status = ItemStatus.DONE
        with session_scope() as session:
            second = EvaluationRepo(session).record(run_id, outcome).evaluated_at

        assert second > first


class TestPromotionChecksTheDeployedCode:
    """Defect 58 turned into a refusal (BR-129).

    On 2026-08-30 run 127 was measured by one build and promoted from a
    container running another. Nothing anywhere could say so; the mismatch
    surfaced only because a later run produced a different number on the same
    corpus. A baseline is what every later run is judged against, so promoting
    one the deployed code cannot reproduce sets the guard against a value that
    no longer exists.
    """

    def _run(self):
        return _mark(
            EvaluationService().run(
                mode=RunMode.RETRIEVAL_ONLY, golden_set_path=str(GOLDEN)
            )
        )

    def test_a_run_records_the_code_that_produced_it(self):
        summary = self._run()
        with session_scope() as session:
            run = EvaluationRepo(session).get_run(summary.run_id)
            assert run.build_id == build_id()

    def test_promoting_a_run_from_other_code_is_refused(self):
        with _baseline_restored():
            summary = self._run()
            with session_scope() as session:
                EvaluationRepo(session).get_run(summary.run_id).build_id = "0" * 12

            with pytest.raises(ConfigurationError) as caught:
                EvaluationService().promote_baseline(summary.run_id)

            message = str(caught.value)
            # The message has to carry the way out, not just the refusal.
            assert "docker compose up -d --build" in message
            assert "--accept-stale" in message

            with session_scope() as session:
                assert EvaluationRepo(session).get_run(summary.run_id).is_baseline is False

    def test_accept_stale_promotes_and_says_so_in_the_row(self):
        """The override exists because a `--full` run costs two days of judge
        quota and code legitimately moves while it runs. It is recorded, so the
        history says the promotion was made knowingly."""
        with _baseline_restored():
            summary = self._run()
            with session_scope() as session:
                EvaluationRepo(session).get_run(summary.run_id).build_id = "0" * 12

            EvaluationService().promote_baseline(summary.run_id, accept_stale=True)

            with session_scope() as session:
                run = EvaluationRepo(session).get_run(summary.run_id)
                assert run.is_baseline is True
                assert "accept-stale" in (run.note or "")

    def test_a_freshly_measured_run_promotes_without_the_flag(self):
        """The gate must not make the ordinary case need an override."""
        with _baseline_restored():
            summary = self._run()
            EvaluationService().promote_baseline(summary.run_id)
            with session_scope() as session:
                assert EvaluationRepo(session).get_run(summary.run_id).is_baseline is True
