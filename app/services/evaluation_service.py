"""S5 EvaluationService - workflows W15~W18 (FR-36~39).

The service calls `QueryService.answer()` and nothing else (BR-115). There is no
evaluation-only retrieval path, no "just this once" flag that skips
verification. DD-22 is the whole reason these numbers mean anything: the moment
the evaluated pipeline differs from the shipped one, the metrics describe
something nobody runs.

Two modes, and the split is drawn along whether a metric needs the model:

  * `retrieval_only` - Recall@k, MRR, refusal accuracy. **Zero LLM calls**,
    whole set, seconds. This is the one that runs every day.
  * `full` - everything, one judge call per answered question on top of the 5.25
    the answer itself costs. Measured against a 20/day free-tier cap that is
    seven days for 25 questions, so it is built to be interrupted and resumed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.llm_trace import CallContext, TracedLlm
from app.core.build import build_id
from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError, QuotaExhaustedError
from app.core.logging import get_logger
from app.core.types import LlmPurpose, Scope
from app.db.engine import session_scope
from app.db.models import ChunkRow, Document, Source
from app.db.repositories.evaluation import EvaluationRepo
from app.db.repositories.traces import LlmCallRepo
from app.evaluation import answer_metrics, reporter, retrieval_metrics
from app.evaluation.golden_set import GoldenSetLoader
from app.evaluation.judge import LLMJudge
from app.evaluation.types import (
    ComparisonReport,
    Expects,
    GoldenQuestion,
    GoldenSet,
    ItemOutcome,
    ItemStatus,
    RetrievedRef,
    RunMode,
    RunStatus,
)
from app.rag import refusal
from app.rag.prompts import shared_repository

log = get_logger(__name__)


def judge_evidence(citations: list[dict]) -> list[str]:
    """One snippet per chunk, in first-cited order (C7).

    `result.citations` holds one row **per sentence per chunk**, so a chunk
    cited by four sentences contributes its snippet four times. The judge sees
    `_render`'s `MAX_EVIDENCE_CHARS` slice of the joined text, and the
    duplicates spend that budget without telling the judge anything new.

    Measured on run 387 sub-07 (query 324): 8 citations over 3 distinct chunks.
    Chunk 17530 repeated 6 times for 6,288 chars on its own, pushing the joined
    length to 9,007 - 3,007 past the 6,000 cap. Sentence 6's evidence (chunk
    17152) sat wholly beyond it, so the judge marked that sentence unfaithful
    for evidence it was never shown. Deduplicated the same rows come to 3,732
    and all three chunks arrive. sub-08 (query 308) had the same shape: 8
    citations, 2 distinct chunks, 7,565 -> 1,235, with sentence 7's evidence
    (chunk 17529) going from cut off to included. The verifier reads whole
    chunks and had judged both sentences supported, so this was a measurement
    defect, not a quality one.

    Deduplicated on `chunk_id` rather than on the snippet string: the same
    chunk can arrive with different snippets, and it is the chunk that is the
    unit of evidence. Rows without a `chunk_id` fall back to the string so an
    unidentified snippet is still not repeated.
    """
    seen: set = set()
    texts: list[str] = []
    for citation in citations:
        snippet = str(citation.get("snippet") or "")
        chunk_id = citation.get("chunk_id")
        key = ("chunk", chunk_id) if chunk_id is not None else ("text", snippet)
        if key in seen:
            continue
        seen.add(key)
        texts.append(snippet)
    return texts


class _NoLLM:
    """BR-119 made enforceable rather than hoped for.

    `--retrieval-only` promises zero model calls. Passing `None` would rely on
    `ENTITY_LLM_ENABLED` staying false, and a rule that depends on a setting
    someone can flip is not a rule - it is a coincidence. Anything that reaches
    a model here raises instead, loudly, in a test rather than on a bill.
    """

    def _refuse(self, *_args, **_kwargs):
        raise AssertionError(
            "retrieval-only 평가가 LLM 을 호출하려 했습니다 (BR-119)"
        )

    generate = _refuse
    generate_structured = _refuse


@dataclass
class RunSummary:
    run_id: int
    status: RunStatus
    metrics: dict
    comparison: ComparisonReport | None


class EvaluationService:
    def __init__(self, settings: Settings | None = None) -> None:
        # No session on the constructor on purpose. A run opens one session per
        # question (BR-117) because it spans days; holding one for the duration
        # would keep a transaction open across an overnight pause.
        self._settings = settings or get_settings()

    # ---- W15 / W16 ----
    def run(self, *, mode: RunMode, golden_set_path: str | None = None) -> RunSummary:
        path = golden_set_path or self._settings.golden_set_path
        with session_scope() as session:
            golden = GoldenSetLoader(session).load(path)
            resolve = self._resolve_documents(session, golden)
            fingerprint = self._corpus_fingerprint(session)

        judge_model = self._settings.judge_model if mode is RunMode.FULL else None
        if mode is RunMode.FULL:
            # BR-122 checked before anything is spent, not on the first judge call.
            self._require_distinct_judge()

        with session_scope() as session:
            run = EvaluationRepo(session).create_run(
                mode=mode,
                golden_set_path=str(golden.path),
                golden_set_hash=golden.sha256,
                question_count=len(golden),
                config=self._config_snapshot(),
                embedding_model=self._settings.embedding_model_id,
                answer_model=(
                    self._settings.resolved_llm_model if mode is RunMode.FULL else None
                ),
                judge_model=judge_model,
                prompt_versions=self._prompt_versions(mode),
                corpus_fingerprint=fingerprint,
                build_id=build_id(),
            )
            run_id = run.id

        return self._execute(run_id, golden, resolve, mode, already_scored=set())

    # ---- W17 ----
    def resume(self, run_id: int) -> RunSummary:
        with session_scope() as session:
            repo = EvaluationRepo(session)
            run = repo.get_run(run_id)
            if run is None:
                raise ConfigurationError(f"실행 {run_id} 을 찾을 수 없습니다")
            if run.status != RunStatus.PARTIAL.value:
                raise ConfigurationError(
                    f"실행 {run_id} 의 상태는 {run.status} 입니다 - partial 만 재개할 수 있습니다"
                )
            mode = RunMode(run.mode)
            path = run.golden_set_path
            stored_hash = run.golden_set_hash
            already = repo.scored_question_ids(run_id)

            golden = GoldenSetLoader(session).load(path)
            if golden.sha256 != stored_hash:
                # Continuing would fuse two different golden sets into one run.
                raise ConfigurationError(
                    "골든셋 파일이 실행 이후 변경되었습니다. 이어서 채점하면 서로 다른 "
                    "골든셋으로 매긴 점수가 한 실행에 섞입니다 - 새 실행을 시작하세요."
                )
            resolve = self._resolve_documents(session, golden)

            # A `--full` run spans days (BR-118), so code can move underneath
            # it. Refusing would be wrong - the answered questions are still
            # answered - but leaving `build_id` naming only the code that
            # started the run would make the row claim more than it knows.
            current = build_id()
            if run.build_id and run.build_id != current:
                log.warning(
                    "evaluation_resumed_on_other_code",
                    extra={"run_id": run_id, "started_with": run.build_id, "now": current},
                )
                run.note = (
                    f"{run.note + ' / ' if run.note else ''}"
                    f"resume: 시작 {run.build_id} / 재개 {current}"
                )

        return self._execute(run_id, golden, resolve, mode, already_scored=already)

    # ---- the loop ----
    def _execute(
        self,
        run_id: int,
        golden: GoldenSet,
        resolve: dict[tuple[str, str], int],
        mode: RunMode,
        already_scored: set[str],
    ) -> RunSummary:
        pending = [q for q in golden.questions if q.id not in already_scored]
        budget = self._settings.evaluation_batch_size or len(pending)
        quota_hit = False
        attempted = 0

        for question in pending:
            if attempted >= budget:
                break
            try:
                outcome = self._score(question, resolve, mode)
            except QuotaExhaustedError as exc:
                # BR-118 - a wait, not a fault. The item is stored so a resume
                # knows where to pick up, and the run ends `partial`.
                log.warning(
                    "evaluation_quota_exhausted",
                    extra={"run_id": run_id, "question_id": question.id, "detail": str(exc)},
                )
                self._store(
                    run_id,
                    ItemOutcome(
                        question_id=question.id,
                        category=question.category,
                        expects=question.expects,
                        status=ItemStatus.QUOTA_EXHAUSTED,
                        error_kind="quota",
                    ),
                )
                quota_hit = True
                break
            except Exception as exc:  # noqa: BLE001 - one question must not end the run
                log.exception("evaluation_item_failed", extra={"question_id": question.id})
                outcome = ItemOutcome(
                    question_id=question.id,
                    category=question.category,
                    expects=question.expects,
                    status=ItemStatus.FAILED,
                    error_kind=type(exc).__name__,
                )
            self._store(run_id, outcome)
            attempted += 1

        return self._finish(run_id, mode, quota_hit)

    def _score(
        self,
        question: GoldenQuestion,
        resolve: dict[tuple[str, str], int],
        mode: RunMode,
    ) -> ItemOutcome:
        started = time.perf_counter()
        if mode is RunMode.RETRIEVAL_ONLY:
            return self._score_retrieval_only(question, resolve, started)
        return self._score_full(question, resolve, started)

    def _score_retrieval_only(
        self, question: GoldenQuestion, resolve: dict, started: float
    ) -> ItemOutcome:
        """BR-119 - not one LLM call.

        `entity_llm=None` rather than trusting `ENTITY_LLM_ENABLED`: the rule
        says this mode never calls a model, and a rule that depends on a setting
        someone can flip is not a rule.
        """
        from app.adapters.embedding_local import shared_adapter
        from app.adapters.tracing import TracedEmbedding
        from app.services.query_service import QueryService, retrieved_refs

        with session_scope() as session:
            guard = _NoLLM()
            service = QueryService(
                session,
                llm=guard,
                entity_llm=guard,
                verify_llm=guard,
                embedder=TracedEmbedding(shared_adapter()),
                settings=self._settings,
            )
            evidence, _mode = service.retrieve(question.question, Scope.public())
            decision = refusal.decide(evidence, self._settings)

        retrieved = [RetrievedRef.from_dict(d) for d in retrieved_refs(evidence)]
        score = retrieval_metrics.score(question.evidence, retrieved, resolve)
        # There is no generation here, so the outcome is what stage one decided.
        outcome = "refused_low_relevance" if decision.refused else "answered"
        return ItemOutcome(
            question_id=question.id,
            category=question.category,
            expects=question.expects,
            status=ItemStatus.DONE,
            outcome=outcome,
            retrieved=retrieved,
            recall_at_5=score.recall.get(5),
            recall_at_10=score.recall.get(10),
            reciprocal_rank=score.reciprocal_rank,
            refusal_correct=answer_metrics.refusal_correct(
                question.expects is Expects.REFUSAL, outcome
            ),
            llm_calls=0,
            total_ms=int((time.perf_counter() - started) * 1000),
        )

    def _score_full(
        self, question: GoldenQuestion, resolve: dict, started: float
    ) -> ItemOutcome:
        from app.adapters.embedding_local import shared_adapter
        from app.adapters.llm_factory import (
            build_entity_llm,
            build_judge_llm,
            build_llm,
            build_verify_llm,
        )
        from app.adapters.tracing import TracedEmbedding
        from app.db.engine import observability_scope
        from app.services.query_service import QueryService

        with observability_scope() as obs, session_scope() as session:
            service = QueryService(
                session,
                llm=build_llm(),
                entity_llm=build_entity_llm(),
                verify_llm=build_verify_llm(),
                embedder=TracedEmbedding(shared_adapter()),
                settings=self._settings,
                obs_session=obs,
            )
            result = service.answer(question.question, Scope.public())
            evidence_texts = judge_evidence(result.citations)
            # The judge call happens inside the observability scope so its row
            # is written with the others, and carries the query it graded.
            judgement = None
            answer_text = " ".join(s.get("text", "") for s in result.sentences).strip()
            if question.wants_answer and answer_text:
                # BR-120 - a refusal question never reaches the judge.
                #
                # BR-95 / FR-41 - and the judge is wrapped like every other
                # call. Left raw it would spend a model's daily quota and leave
                # no `llm_call` row, so `/usage` would under-report and a judge
                # that had started failing would be invisible. Built here rather
                # than above because the context carries the query id, and that
                # id does not exist until the answer has been written.
                context = CallContext()
                context.query_id = result.query_id
                judge_llm = TracedLlm(
                    build_judge_llm(self._settings),
                    LlmCallRepo(obs),
                    LlmPurpose.JUDGE,
                    context,
                    self._settings.llm_provider,
                )
                judgement = LLMJudge(judge_llm, settings=self._settings).judge(
                    question, answer_text, evidence_texts
                )

        retrieved = [RetrievedRef.from_dict(d) for d in result.retrieved]
        score = retrieval_metrics.score(question.evidence, retrieved, resolve)
        cited = [
            RetrievedRef(
                rank=index,
                chunk_id=int(c["chunk_id"]),
                document_id=self._document_of(retrieved, int(c["chunk_id"])),
                section_code=c.get("section_code"),
            )
            for index, c in enumerate(result.citations)
            if c.get("chunk_id") is not None
        ]

        # Read back rather than assumed. Storing only the judge call would report
        # 1 where the real cost is 6.25, and that ratio is the fact the whole
        # unit is designed around - a cost figure that omits 84% of the spend is
        # worse than none. Counted after the scope closed, so the judge row is
        # committed and included.
        llm_calls = self._calls_for(result.query_id)

        return ItemOutcome(
            question_id=question.id,
            category=question.category,
            expects=question.expects,
            status=ItemStatus.DONE,
            query_id=result.query_id,
            outcome=result.outcome.value,
            retrieved=retrieved,
            recall_at_5=score.recall.get(5),
            recall_at_10=score.recall.get(10),
            reciprocal_rank=score.reciprocal_rank,
            citation_precision=answer_metrics.citation_precision(
                question.evidence, cited, resolve
            ),
            refusal_correct=answer_metrics.refusal_correct(
                question.expects is Expects.REFUSAL, result.outcome.value
            ),
            judgement=judgement,
            llm_calls=llm_calls,
            total_ms=int((time.perf_counter() - started) * 1000),
        )

    @staticmethod
    def _calls_for(query_id: int | None) -> int:
        """BR-95 already records every call; this just reads the count back."""
        if query_id is None:
            return 0
        from app.db.models import LlmCallRow

        with session_scope() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(LlmCallRow)
                    .where(LlmCallRow.query_id == query_id)
                )
                or 0
            )

    @staticmethod
    def _document_of(retrieved: list[RetrievedRef], chunk_id: int) -> int:
        for ref in retrieved:
            if ref.chunk_id == chunk_id:
                return ref.document_id
        return -1

    # ---- persistence ----
    def _store(self, run_id: int, outcome: ItemOutcome) -> None:
        # One question, one transaction (BR-117).
        with session_scope() as session:
            EvaluationRepo(session).record(run_id, outcome)

    def _finish(self, run_id: int, mode: RunMode, quota_hit: bool) -> RunSummary:
        with session_scope() as session:
            repo = EvaluationRepo(session)
            run = repo.get_run(run_id)
            items = repo.items(run_id)
            scored = sum(1 for i in items if i.status in ("done", "skipped"))
            status = (
                RunStatus.PARTIAL
                if quota_hit or scored < run.question_count
                else RunStatus.SUCCEEDED
            )
            metrics = reporter.aggregate(items, mode.value, run.question_count)
            repo.finish_run(
                run,
                status=status,
                metrics=metrics,
                llm_calls=sum(int(i.llm_calls or 0) for i in items),
            )
            baseline = repo.latest_baseline(run.mode)
            if baseline is not None and baseline.id == run.id:
                baseline = None
            comparison = reporter.compare(run, baseline)
            repo.attach_baseline(run, baseline.id if baseline else None)
            return RunSummary(
                run_id=run_id, status=status, metrics=metrics, comparison=comparison
            )

    # ---- W18 ----
    def compare(self, run_id: int, baseline_id: int | None = None) -> ComparisonReport:
        with session_scope() as session:
            repo = EvaluationRepo(session)
            run = repo.get_run(run_id)
            if run is None:
                raise ConfigurationError(f"실행 {run_id} 을 찾을 수 없습니다")
            baseline = (
                repo.get_run(baseline_id)
                if baseline_id
                else repo.latest_baseline(run.mode)
            )
            if baseline is not None and baseline.id == run.id:
                baseline = None
            return reporter.compare(run, baseline)

    def promote_baseline(self, run_id: int, *, accept_stale: bool = False) -> None:
        """BR-129 - a person promotes, and this is where that act is checked.

        The build-id gate is defect 58 turned into a refusal. On 2026-08-30 a
        run measured by one build was promoted from a container running
        another, and nothing anywhere could say so. A baseline is the number
        every later run is judged against; promoting one that the deployed code
        cannot reproduce sets the guard against a value that no longer exists.

        `accept_stale` exists because a `--full` run costs two days of judge
        quota and code legitimately moves while it runs. It is a deliberate
        override, not a default: the reason is printed and the run is marked,
        so the history says the promotion was made knowingly.
        """
        with session_scope() as session:
            repo = EvaluationRepo(session)
            run = repo.get_run(run_id)
            if run is None:
                raise ConfigurationError(f"실행 {run_id} 을 찾을 수 없습니다")
            if run.status not in (RunStatus.SUCCEEDED.value, RunStatus.PARTIAL.value):
                raise ConfigurationError(
                    f"실행 {run_id} 은 {run.status} 상태라 기준선이 될 수 없습니다"
                )
            current = build_id()
            if run.build_id != current and not accept_stale:
                measured = run.build_id or "미기록"
                raise ConfigurationError(
                    "\n".join(
                        (
                            f"실행 {run_id} 은 코드 {measured} 로 측정됐고 "
                            f"지금 도는 코드는 {current} 입니다.",
                            "  재빌드 후 컨테이너를 재생성하지 않으면 이 상태가 됩니다 (결함 58):",
                            "    docker compose up -d --build app worker",
                            "  그 뒤 다시 측정해 승격하십시오. 검색전용 실행은 20초입니다.",
                            "  --full 은 측정에 이틀이 드므로 --accept-stale 로 넘길 수 있습니다.",
                        )
                    )
                )
            if run.build_id != current:
                run.note = (
                    f"{run.note + ' / ' if run.note else ''}"
                    f"accept-stale: 측정 {run.build_id or '미기록'} / 승격 시점 {current}"
                )
            repo.set_baseline(run, True)

    def list_runs(self, limit: int = 20) -> list[dict]:
        with session_scope() as session:
            return [
                {
                    "id": r.id,
                    "mode": r.mode,
                    "status": r.status,
                    "is_baseline": r.is_baseline,
                    "questions": r.question_count,
                    "llm_calls": r.llm_calls,
                    "started_at": r.started_at,
                    "metrics": r.metrics,
                    # The integration suite labels the runs it creates, and 103
                    # of the first 141 rows carry that label. Withholding it
                    # from `--list` made the history 73% unmarked noise in the
                    # one place a person actually reads before promoting.
                    "note": r.note,
                    "build_id": r.build_id,
                }
                for r in EvaluationRepo(session).list_runs(limit)
            ]

    # ---- context ----
    def _require_distinct_judge(self) -> None:
        from app.adapters.llm_factory import build_judge_llm

        build_judge_llm(self._settings)  # raises when misconfigured (BR-122)

    def _config_snapshot(self) -> dict:
        """`RetrievalConfig` does not exist; `Settings` is what the pipeline reads.

        Snapshotting the actual fields keeps the run honest about what produced
        its numbers, which is what `incomparable` later depends on.
        """
        s = self._settings
        return {
            "fusion_top_k": s.fusion_top_k,
            "final_top_k": s.final_top_k,
            "rrf_k": s.rrf_k,
            "refusal_score_threshold": s.refusal_score_threshold,
            "rerank_enabled": bool(getattr(s, "rerank_enabled", False)),
            "entity_llm_enabled": bool(getattr(s, "entity_llm_enabled", False)),
        }

    def _prompt_versions(self, mode: RunMode) -> dict:
        if mode is RunMode.RETRIEVAL_ONLY:
            return {}
        repo = shared_repository()
        return {name: repo.get(name).version for name in ("answer", "verify", "judge")}

    @staticmethod
    def _corpus_fingerprint(session: Session) -> dict:
        latest = session.scalar(select(func.max(Document.revised_at)))
        return {
            "documents": session.scalar(select(func.count()).select_from(Document)) or 0,
            "chunks": session.scalar(select(func.count()).select_from(ChunkRow)) or 0,
            "latest_revised_at": latest.isoformat() if latest else None,
        }

    @staticmethod
    def _resolve_documents(
        session: Session, golden: GoldenSet
    ) -> dict[tuple[str, str], int]:
        """One query for every reference in the set.

        The metric functions stay pure by taking this map instead of a session -
        which is what lets C45 and C46 be unit-tested without a database (NFR-28).
        """
        wanted = {
            (ref.source, ref.external_id)
            for question in golden.questions
            for ref in question.evidence
        }
        if not wanted:
            return {}
        rows = session.execute(
            select(Source.source_id, Document.external_id, Document.id)
            .join(Document, Document.source_id == Source.id)
            .where(Document.external_id.in_({external for _s, external in wanted}))
        ).all()
        return {
            (source_id, external_id): document_id
            for source_id, external_id, document_id in rows
            if (source_id, external_id) in wanted
        }
