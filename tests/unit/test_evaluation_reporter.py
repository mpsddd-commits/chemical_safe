"""C48 — aggregation, comparison, and the verdict that becomes an exit code.

The two behaviours worth guarding are not arithmetic.

A **regression is measured against a promoted baseline**, never against an
absolute floor (never measured on this corpus, so a first run below it paints CI
red forever) and never against the previous run (slow decay always passes).

And **two runs that measured different things are not compared**. This corpus
has changed four times already; a delta across that boundary looks like quality
and is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.evaluation import reporter
from app.evaluation.types import Verdict


@dataclass
class FakeItem:
    status: str = "done"
    expects: str = "answer"
    outcome: str | None = "answered"
    recall_at_5: float | None = 1.0
    recall_at_10: float | None = 1.0
    reciprocal_rank: float | None = 1.0
    citation_precision: float | None = 1.0
    judge_correct: bool | None = True
    judge_faithful: bool | None = True
    llm_calls: int = 6
    # Five, because that is what the pipeline actually hands out - `final_top_k`
    # caps the evidence list and nothing downstream sees more.
    retrieved: list = field(default_factory=lambda: [{}] * 5)


@dataclass
class FakeRun:
    id: int
    metrics: dict
    golden_set_hash: str = "h"
    answer_model: str = "m"
    judge_model: str = "j"
    prompt_versions: dict = field(default_factory=lambda: {"answer": "1.0.0"})
    config: dict = field(default_factory=lambda: {"final_top_k": 5})
    corpus_fingerprint: dict = field(default_factory=lambda: {"chunks": 1633})


def _metrics(**over) -> dict:
    base = {
        "retrieval": {"recall_at_5": 0.8, "recall_at_10": 0.9, "mrr": 0.7},
        "answer": {"accuracy": 0.8, "citation_precision": 0.9},
        "judge": {"faithfulness": 0.95, "judged": 25},
        "refusal": {"accuracy": 1.0, "false_refusal": 0.04},
        "counts": {"total": 30, "done": 30, "failed": 0, "quota_exhausted": 0},
        "cost": {"llm_calls": 131},
    }
    for path, value in over.items():
        group, name = path.split(".")
        base[group][name] = value
    return base


class TestAggregate:
    def test_recall_at_10_is_none_when_the_list_is_only_five_deep(self):
        """Defect 49 - measured on the first real run: `retrieved` is always 5.

        BR-124 asked for Recall@5 and Recall@10 so that a gap between them would
        point at ranking. With `final_top_k=5` the two can never differ, so the
        second number was a copy of the first wearing a label that invited a
        diagnosis it could not support. Reporting nothing is the honest form.
        """
        metrics = reporter.aggregate([FakeItem()], "retrieval_only")
        assert metrics["retrieval"]["depth"] == 5
        assert metrics["retrieval"]["recall_at_5"] == 1.0
        assert metrics["retrieval"]["recall_at_10"] is None

    def test_recall_at_10_is_reported_when_the_list_goes_that_deep(self):
        item = FakeItem()
        item.retrieved = [{}] * 12
        metrics = reporter.aggregate([item], "retrieval_only")
        assert metrics["retrieval"]["recall_at_10"] == 1.0

    def test_the_report_says_why_recall_at_10_is_missing(self):
        text = reporter.render_metrics(reporter.aggregate([FakeItem()], "retrieval_only"))
        assert "Recall@10 은 측정할 수 없습니다" in text

    def test_retrieval_only_reports_no_answer_metrics(self):
        """Absent, not zero.

        u1 read `substances = 0` as "nothing collected yet" when it meant
        "collection does not populate the master" (defect 40). A 0.0 accuracy on
        a run that never generated an answer is the same misreading waiting to
        happen.
        """
        metrics = reporter.aggregate([FakeItem()], "retrieval_only")
        assert "answer" not in metrics
        assert "judge" not in metrics
        assert metrics["retrieval"]["recall_at_5"] == 1.0

    def test_full_reports_answer_metrics(self):
        metrics = reporter.aggregate([FakeItem()], "full")
        assert metrics["answer"]["accuracy"] == 1.0
        assert metrics["judge"]["faithfulness"] == 1.0

    def test_unmeasured_metric_is_none_not_zero(self):
        item = FakeItem(judge_correct=None, judge_faithful=None, citation_precision=None)
        metrics = reporter.aggregate([item], "full")
        assert metrics["answer"]["accuracy"] is None
        assert metrics["answer"]["citation_precision"] is None
        assert metrics["judge"]["judged"] == 0

    def test_unscored_items_do_not_enter_the_averages(self):
        items = [FakeItem(), FakeItem(status="quota_exhausted", recall_at_5=None)]
        metrics = reporter.aggregate(items, "retrieval_only")
        assert metrics["retrieval"]["recall_at_5"] == 1.0
        assert metrics["counts"]["quota_exhausted"] == 1
        assert metrics["counts"]["done"] == 1

    def test_a_partial_run_reports_the_set_size_not_the_row_count(self):
        """Measured on run 10: 20 scored of 30, and the report said "문항 21".

        The row count is what a partial run wrote, not how big the golden set
        is, and printing it under that label told the reader the set had shrunk.
        """
        items = [FakeItem(), FakeItem(status="quota_exhausted")]
        metrics = reporter.aggregate(items, "full", question_count=30)
        assert metrics["counts"]["questions"] == 30
        assert metrics["counts"]["attempted"] == 2
        assert metrics["counts"]["done"] == 1
        assert "골든셋 30문항" in reporter.render_metrics(metrics)
        assert "미채점 29" in reporter.render_metrics(metrics)

    def test_refusal_rates_are_both_present(self):
        items = [
            FakeItem(expects="refusal", outcome="refused_low_relevance"),
            FakeItem(expects="answer", outcome="answered"),
        ]
        metrics = reporter.aggregate(items, "retrieval_only")
        assert metrics["refusal"]["accuracy"] == 1.0
        assert metrics["refusal"]["false_refusal"] == 0.0

    def test_llm_calls_are_summed_over_every_item(self):
        items = [FakeItem(llm_calls=6), FakeItem(status="failed", llm_calls=1)]
        assert reporter.aggregate(items, "full")["cost"]["llm_calls"] == 7


class TestCompare:
    def test_no_baseline_is_not_a_regression(self):
        report = reporter.compare(FakeRun(1, _metrics()), None)
        assert report.verdict is Verdict.NO_BASELINE

    def test_identical_runs_are_ok(self):
        report = reporter.compare(FakeRun(2, _metrics()), FakeRun(1, _metrics()))
        assert report.verdict is Verdict.OK

    def test_a_small_drop_is_within_tolerance(self):
        report = reporter.compare(
            FakeRun(2, _metrics(**{"retrieval.recall_at_5": 0.77})),
            FakeRun(1, _metrics()),
        )
        assert report.verdict is Verdict.OK

    def test_a_large_drop_is_a_regression(self):
        report = reporter.compare(
            FakeRun(2, _metrics(**{"retrieval.recall_at_5": 0.70})),
            FakeRun(1, _metrics()),
        )
        assert report.verdict is Verdict.REGRESSION
        assert any(d.regressed for d in report.deltas)

    def test_improvement_is_never_a_regression(self):
        report = reporter.compare(
            FakeRun(2, _metrics(**{"retrieval.recall_at_5": 0.99})),
            FakeRun(1, _metrics()),
        )
        assert report.verdict is Verdict.OK

    def test_a_single_missed_refusal_is_a_regression(self):
        """Tolerance 0 on purpose — five refusal questions in thirty, so one
        miss is 0.20, and SC-3 is the safety promise of the system."""
        report = reporter.compare(
            FakeRun(2, _metrics(**{"refusal.accuracy": 0.8})),
            FakeRun(1, _metrics()),
        )
        assert report.verdict is Verdict.REGRESSION

    def test_rising_false_refusal_is_a_regression(self):
        """The one metric where up is bad."""
        report = reporter.compare(
            FakeRun(2, _metrics(**{"refusal.false_refusal": 0.20})),
            FakeRun(1, _metrics()),
        )
        assert report.verdict is Verdict.REGRESSION

    def test_a_changed_corpus_makes_the_runs_incomparable(self):
        current = FakeRun(2, _metrics(**{"retrieval.recall_at_5": 0.10}))
        current.corpus_fingerprint = {"chunks": 9999}
        report = reporter.compare(current, FakeRun(1, _metrics()))
        assert report.verdict is Verdict.INCOMPARABLE
        assert report.warnings
        # The deltas are still shown — that is how you find out whether the
        # corpus change explains the movement.
        assert report.deltas

    def test_a_changed_prompt_makes_the_runs_incomparable(self):
        current = FakeRun(2, _metrics())
        current.prompt_versions = {"answer": "1.1.0"}
        assert reporter.compare(current, FakeRun(1, _metrics())).verdict is (
            Verdict.INCOMPARABLE
        )

    def test_a_changed_golden_set_makes_the_runs_incomparable(self):
        current = FakeRun(2, _metrics())
        current.golden_set_hash = "different"
        assert reporter.compare(current, FakeRun(1, _metrics())).verdict is (
            Verdict.INCOMPARABLE
        )

    def test_a_missing_metric_does_not_count_as_a_drop(self):
        """A retrieval-only run compared to a full baseline: no accuracy figure
        is not an accuracy of zero."""
        current = FakeRun(2, {k: v for k, v in _metrics().items() if k != "answer"})
        report = reporter.compare(current, FakeRun(1, _metrics()))
        accuracy = next(d for d in report.deltas if d.name == "answer.accuracy")
        assert accuracy.delta is None
        assert not accuracy.regressed


class TestRendering:
    def test_metrics_render_missing_values_as_dashes(self):
        text = reporter.render_metrics(reporter.aggregate([FakeItem()], "retrieval_only"))
        assert "--" in text
        assert "Recall@5" in text

    def test_comparison_marks_the_regressed_row(self):
        report = reporter.compare(
            FakeRun(2, _metrics(**{"retrieval.mrr": 0.50})), FakeRun(1, _metrics())
        )
        assert "회귀" in reporter.render_comparison(report)
