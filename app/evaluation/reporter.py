"""C48 EvaluationReporter - FR-39, NFR-26, BR-129·BR-130.

Aggregation, the baseline comparison, and the verdict that becomes an exit code.

Two decisions here are worth more than the arithmetic.

**A regression is a drop from a promoted baseline, not from the last run and not
from an absolute floor.** An absolute floor cannot be used yet: NFR-5's 95% and
NFR-6's 5% have never been measured on this corpus, and a first run below them
would paint CI red forever - the same mistake as u2 defect 34, where a timeout
was derived from a budget instead of a measurement and killed a successful call.
Comparing against the previous run instead misses slow decay, because a metric
that falls a little every time always passes.

**Two runs that measured different things are not compared.** If the corpus,
the models or the prompts differ, the delta is still shown but the verdict is
`incomparable`. This corpus has already changed four times; subtracting across
that boundary produces a number that looks like quality and is not.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.evaluation.answer_metrics import refusal_rates
from app.evaluation.types import ComparisonReport, MetricDelta, Verdict

# Allowed drop per metric (BR-130). Provisional until the first `--full` run
# produces a baseline - an unmeasured threshold is a guess, and this file says
# so rather than presenting these as calibrated.
TOLERANCE: dict[str, float] = {
    "retrieval.recall_at_5": 0.05,
    "retrieval.recall_at_10": 0.05,
    "retrieval.mrr": 0.05,
    "answer.accuracy": 0.05,
    "answer.citation_precision": 0.03,
    "judge.faithfulness": 0.05,
    # Zero on purpose: SC-3 (do not answer without grounds) is the safety
    # promise of this system, and with five refusal questions in thirty a single
    # miss is 0.20. There is no tolerance band that is both meaningful and
    # non-trivial at this set size.
    "refusal.accuracy": 0.0,
    "refusal.false_refusal": 0.05,
}

LOWER_IS_BETTER = {"refusal.false_refusal"}

# Fields that must match for two runs to be comparable at all.
_COMPARABLE_FIELDS = (
    "golden_set_hash",
    "answer_model",
    "judge_model",
    "prompt_versions",
    "config",
    "corpus_fingerprint",
)


def _mean(values: Sequence[float | None]) -> float | None:
    present = [float(v) for v in values if v is not None]
    if not present:
        # None, never 0.0. A metric that was not measured and a metric that
        # measured zero are different facts - u1 read `substances = 0` as
        # "nothing collected yet" when it meant "collection does not populate
        # the master" (defect 40), and that is the shape of mistake this avoids.
        return None
    return round(sum(present) / len(present), 3)


def aggregate(items: Sequence, mode: str, question_count: int | None = None) -> dict:
    """Roll item rows up into `evaluation_run.metrics`.

    `items` are ORM rows or anything with the same attribute names.
    """
    done = [i for i in items if i.status == "done"]
    answered = [i for i in done if i.expects == "answer"]
    # How deep the candidate list actually went. Measured 2026-08-28: exactly 5,
    # because the pipeline hands out `final_top_k` items of evidence and nothing
    # downstream ever sees more. Recall@10 over a five-item list is Recall@5
    # under a second name, and BR-124 wanted the two to *diagnose* ranking -
    # a comparison that cannot vary diagnoses nothing.
    depth = max((len(i.retrieved or []) for i in done), default=0)

    metrics: dict = {
        "counts": {
            # The golden set's size, not the number of rows written. A partial
            # run has fewer rows than questions, and reporting the row count as
            # "문항" told the reader the set had shrunk.
            "questions": question_count if question_count is not None else len(items),
            "attempted": len(items),
            "done": len(done),
            "answer_questions": len(answered),
            "refusal_questions": len(done) - len(answered),
            "failed": sum(1 for i in items if i.status == "failed"),
            "quota_exhausted": sum(1 for i in items if i.status == "quota_exhausted"),
        },
        "retrieval": {
            "depth": depth,
            "recall_at_5": _mean([i.recall_at_5 for i in done]) if depth >= 5 else None,
            # None rather than the duplicate value. "Not measurable at this
            # depth" and "measured, and identical" are different facts.
            "recall_at_10": (
                _mean([i.recall_at_10 for i in done]) if depth >= 10 else None
            ),
            "mrr": _mean([i.reciprocal_rank for i in done]),
        },
        "refusal": refusal_rates([(i.expects == "refusal", i.outcome) for i in done]),
        "cost": {
            "llm_calls": sum(int(i.llm_calls or 0) for i in items),
        },
    }

    if mode == "full":
        judged = [i for i in answered if i.judge_correct is not None]
        metrics["answer"] = {
            "accuracy": (
                round(sum(1 for i in judged if i.judge_correct) / len(judged), 3)
                if judged
                else None
            ),
            "citation_precision": _mean([i.citation_precision for i in answered]),
        }
        metrics["judge"] = {
            "faithfulness": (
                round(sum(1 for i in judged if i.judge_faithful) / len(judged), 3)
                if judged
                else None
            ),
            "judged": len(judged),
        }
    # A retrieval_only run carries no `answer`/`judge` keys at all. Emitting
    # zeros would read as "measured, and bad".
    return metrics


def _pick(metrics: dict, path: str) -> float | None:
    group, _, name = path.partition(".")
    value = (metrics.get(group) or {}).get(name)
    return None if value is None else float(value)


def compare(run, baseline) -> ComparisonReport:
    if baseline is None:
        return ComparisonReport(
            run_id=run.id,
            baseline_id=None,
            verdict=Verdict.NO_BASELINE,
            warnings=("비교할 기준선이 없습니다. --promote 로 기준선을 지정하세요.",),
        )

    warnings: list[str] = []
    for field in _COMPARABLE_FIELDS:
        if getattr(run, field, None) != getattr(baseline, field, None):
            warnings.append(f"{field} 가 기준선과 다릅니다")

    deltas = tuple(
        MetricDelta(
            name=path,
            baseline=_pick(baseline.metrics or {}, path),
            current=_pick(run.metrics or {}, path),
            tolerance=tolerance,
            higher_is_better=path not in LOWER_IS_BETTER,
        )
        for path, tolerance in TOLERANCE.items()
    )

    if warnings:
        # Deltas are still shown - seeing them is how you find out whether the
        # corpus change explains the movement - but no regression is declared.
        return ComparisonReport(
            run_id=run.id,
            baseline_id=baseline.id,
            verdict=Verdict.INCOMPARABLE,
            deltas=deltas,
            warnings=tuple(warnings),
        )

    regressed = [d for d in deltas if d.regressed]
    return ComparisonReport(
        run_id=run.id,
        baseline_id=baseline.id,
        verdict=Verdict.REGRESSION if regressed else Verdict.OK,
        deltas=deltas,
        warnings=(),
    )


_LABEL = {
    "retrieval.recall_at_5": "Recall@5",
    "retrieval.recall_at_10": "Recall@10",
    "retrieval.mrr": "MRR",
    "answer.accuracy": "정답률",
    "answer.citation_precision": "인용 정확도",
    "judge.faithfulness": "충실도",
    "refusal.accuracy": "거부 정확도",
    "refusal.false_refusal": "오거부율",
}


def render_metrics(metrics: dict) -> str:
    lines: list[str] = []
    counts = metrics.get("counts") or {}
    depth = (metrics.get("retrieval") or {}).get("depth")
    questions = counts.get("questions", 0)
    done = counts.get("done", 0)
    lines.append(
        f"골든셋 {questions}문항 / 채점 {done} / 미채점 {max(questions - done, 0)} / "
        f"실패 {counts.get('failed', 0)} / 할당량중단 {counts.get('quota_exhausted', 0)}"
    )
    for path, label in _LABEL.items():
        value = _pick(metrics, path)
        # "정보 없음" rather than 0.000, for the same reason the aggregate keeps
        # None (BR-102's habit, applied to a report instead of a card).
        lines.append(f"  {label:12s} {'  --  ' if value is None else f'{value:.3f}'}")
    cost = (metrics.get("cost") or {}).get("llm_calls")
    lines.append(f"  {'LLM 호출':12s} {cost}")
    if depth is not None and 0 < depth < 10:
        lines.append(
            f"  ⚠ 후보 목록이 {depth}건이라 Recall@10 은 측정할 수 없습니다 "
            f"(FINAL_TOP_K={depth})"
        )
    return "\n".join(lines)


def render_comparison(report: ComparisonReport) -> str:
    lines = [f"실행 {report.run_id} vs 기준선 {report.baseline_id}"]
    for delta in report.deltas:
        label = _LABEL.get(delta.name, delta.name)
        base = "  --  " if delta.baseline is None else f"{delta.baseline:.3f}"
        cur = "  --  " if delta.current is None else f"{delta.current:.3f}"
        diff = "  --  " if delta.delta is None else f"{delta.delta:+.3f}"
        mark = "  ← 회귀" if delta.regressed else ""
        lines.append(f"  {label:12s} {base} → {cur}   {diff}{mark}")
    for warning in report.warnings:
        lines.append(f"  ⚠ {warning}")
    lines.append(f"판정: {report.verdict.value}")
    return "\n".join(lines)
