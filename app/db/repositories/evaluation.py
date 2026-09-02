"""EvaluationRepo - persistence for E19/E20.

The only interesting thing here is what is *not* here: no transaction control.
A run spans days and the caller opens one session per question (BR-117), so this
repository never commits - it writes into whatever transaction it was handed,
the same discipline u1's repositories keep.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import EvaluationItem, EvaluationRun
from app.evaluation.types import ItemOutcome, RunMode, RunStatus


class EvaluationRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    # ---- run ----
    def create_run(
        self,
        *,
        mode: RunMode,
        golden_set_path: str,
        golden_set_hash: str,
        question_count: int,
        config: dict,
        embedding_model: str | None,
        answer_model: str | None,
        judge_model: str | None,
        prompt_versions: dict,
        corpus_fingerprint: dict,
        build_id: str | None = None,
    ) -> EvaluationRun:
        run = EvaluationRun(
            mode=mode.value,
            status=RunStatus.RUNNING.value,
            golden_set_path=golden_set_path,
            golden_set_hash=golden_set_hash,
            question_count=question_count,
            config=config,
            embedding_model=embedding_model,
            answer_model=answer_model,
            judge_model=judge_model,
            prompt_versions=prompt_versions,
            corpus_fingerprint=corpus_fingerprint,
            build_id=build_id,
            metrics={},
        )
        self._s.add(run)
        self._s.flush()
        return run

    def get_run(self, run_id: int) -> EvaluationRun | None:
        return self._s.get(EvaluationRun, run_id)

    def latest_baseline(self, mode: str | None = None) -> EvaluationRun | None:
        """The promoted baseline **for this mode**.

        One baseline per mode, not one overall. A `--retrieval-only` run has no
        answer model, no judge model and no prompt versions, so measured against
        a `full` baseline it differs on three fields and every daily run comes
        back `incomparable` - the regression guard that the two-tier split
        exists to provide would never once fire. Measured on run 48: identical
        Recall and MRR, and a 거부 정확도 "drop" of 0.200 that was only the
        absence of stage-two verification.
        """
        stmt = select(EvaluationRun).where(EvaluationRun.is_baseline.is_(True))
        if mode is not None:
            stmt = stmt.where(EvaluationRun.mode == mode)
        return self._s.scalar(stmt.order_by(desc(EvaluationRun.finished_at)).limit(1))

    def list_runs(self, limit: int = 20) -> list[EvaluationRun]:
        return list(
            self._s.scalars(
                select(EvaluationRun).order_by(desc(EvaluationRun.id)).limit(limit)
            )
        )

    def finish_run(
        self, run: EvaluationRun, *, status: RunStatus, metrics: dict, llm_calls: int
    ) -> None:
        run.status = status.value
        run.metrics = metrics
        run.llm_calls = llm_calls
        run.finished_at = datetime.now(UTC)
        self._s.flush()

    def set_baseline(self, run: EvaluationRun, value: bool = True) -> None:
        """BR-129 - promotion is an explicit act, and only one run holds it.

        Clearing the others is what makes `latest_baseline()` unambiguous; two
        baselines would make the comparison silently depend on ordering.
        """
        if value:
            # Only within the same mode. A retrieval-only baseline and a full
            # baseline describe different amounts of pipeline and both are
            # wanted - the daily guard needs the first, the release check the
            # second.
            for other in self._s.scalars(
                select(EvaluationRun).where(
                    EvaluationRun.is_baseline.is_(True),
                    EvaluationRun.mode == run.mode,
                )
            ):
                other.is_baseline = False
        run.is_baseline = value
        self._s.flush()

    def attach_baseline(self, run: EvaluationRun, baseline_id: int | None) -> None:
        run.baseline_id = baseline_id
        self._s.flush()

    # ---- item ----
    def items(self, run_id: int) -> list[EvaluationItem]:
        return list(
            self._s.scalars(
                select(EvaluationItem)
                .where(EvaluationItem.run_id == run_id)
                .order_by(EvaluationItem.id)
            )
        )

    def scored_question_ids(self, run_id: int) -> set[str]:
        """Which questions a resume must not touch again (BR-117)."""
        return set(
            self._s.scalars(
                select(EvaluationItem.question_id).where(
                    EvaluationItem.run_id == run_id,
                    EvaluationItem.status.in_(("done", "skipped")),
                )
            )
        )

    def record(self, run_id: int, outcome: ItemOutcome) -> EvaluationItem:
        existing = self._s.scalar(
            select(EvaluationItem).where(
                EvaluationItem.run_id == run_id,
                EvaluationItem.question_id == outcome.question_id,
            )
        )
        row = existing or EvaluationItem(run_id=run_id, question_id=outcome.question_id)
        row.category = outcome.category
        row.expects = outcome.expects.value
        row.status = outcome.status.value
        row.query_id = outcome.query_id
        row.outcome = outcome.outcome
        row.retrieved = [ref.as_dict() for ref in outcome.retrieved]
        row.recall_at_5 = outcome.recall_at_5
        row.recall_at_10 = outcome.recall_at_10
        row.reciprocal_rank = outcome.reciprocal_rank
        row.citation_precision = outcome.citation_precision
        row.refusal_correct = outcome.refusal_correct
        row.judge_correct = outcome.judgement.correct if outcome.judgement else None
        row.judge_faithful = outcome.judgement.faithful if outcome.judgement else None
        row.judge_reason = outcome.judgement.reason if outcome.judgement else None
        row.llm_calls = outcome.llm_calls
        row.total_ms = outcome.total_ms
        row.error_kind = outcome.error_kind
        # When a resume re-scores an item, the timestamp must move with it.
        # `server_default=now()` only fires on insert, so a question that failed
        # on quota one day and was scored the next kept the *failure's* date -
        # measured on run 10, where inc-01 was scored on 08-29 and still claimed
        # 08-28. For a unit whose purpose is attributing change over time, a
        # timestamp that lies about when the measurement happened is not a
        # cosmetic problem.
        row.evaluated_at = datetime.now(UTC)
        if existing is None:
            self._s.add(row)
        self._s.flush()
        return row
