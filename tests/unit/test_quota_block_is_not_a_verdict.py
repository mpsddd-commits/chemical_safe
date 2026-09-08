"""An interrupted measurement is not a product result — C15.

Measured on baseline 609 (2026-09-08). The verifier catches `QuotaExhaustedError`
and returns `UNVERIFIED` with `unverified_by_quota=True`, which is right (BR-87):
one sentence must not kill a query. But the fact stopped there. `QueryResult`
carried the count only into an SSE frame, and the evaluation scored whatever came
back as if the pipeline had run whole.

    질의        verify 실패/성공   609 이 기록한 것
    msds-03         1 / 0        refused_unsupported, 오거부 3/25 에 포함
    msds-02         5 / 8        answered_partial
    sub-07          2 / 7        answered_partial

`metrics.counts.quota_exhausted` for that run was **0** — three interruptions
reported as a clean 30/30. msds-03's one sentence read
"톨루엔의 국내 노출기준은 TWA 50 ppm, STEL 150 ppm입니다", which is correct; the
false-refusal rate should have been 2/25 = 0.080, not 3/25 = 0.120.

`verifier.py` already says the screen must not show the two as one. These tests
pin the rest of the path to the same rule.
"""

from __future__ import annotations

from contextlib import contextmanager

from app.core.types import (
    AnswerOutcome,
    DocType,
    RefusalReason,
    RetrievalMode,
    SupportVerdict,
)
from app.evaluation.types import Expects, GoldenQuestion, ItemStatus
from app.rag.types import AnswerSentence, Evidence
from app.rag.verifier import VerifiedSentence
from app.services.query_service import QueryService


class FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = 1

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class FakeGenerator:
    def __init__(self, sentences: list[AnswerSentence]) -> None:
        self._sentences = sentences

    def generate(self, question, evidence, on_delta=None):
        from app.rag.generator import GenerationOutcome

        return GenerationOutcome(sentences=self._sentences)


class FakeVerifier:
    """Verdicts as `(verdict, blocked_by_quota)`, in order."""

    def __init__(self, verdicts: list[tuple[SupportVerdict, bool]]) -> None:
        self._verdicts = verdicts

    def verify_all(self, sentences, evidence_by_id):
        return [
            VerifiedSentence(sentence, verdict, unverified_by_quota=blocked)
            for sentence, (verdict, blocked) in zip(
                sentences, self._verdicts, strict=True
            )
        ]


def _evidence(chunk_id: int = 11) -> Evidence:
    """`law` on purpose: a subject-less MSDS chunk is refused by BR-73a first."""
    return Evidence(
        chunk_id=chunk_id,
        document_id=1,
        source_url="https://example.test/law",
        document_title="산업안전보건법",
        section_code="law_90",
        section_title="제90조",
        text="사업주는 물질안전보건자료를 게시하여야 한다.",
        start_offset=0,
        end_offset=30,
        score=0.9,
        doc_type=DocType.LAW,
        relevance=0.9,
    )


def _answer(verdicts: list[tuple[SupportVerdict, bool]]):
    sentences = [
        AnswerSentence(text=f"문장 {i}.", chunk_ids=[11]) for i in range(len(verdicts))
    ]
    service = QueryService(
        FakeSession(), llm=object(), embedder=object(), obs_session=FakeSession()
    )
    evidence = [_evidence()]
    service.retrieve = lambda _q, _s: (evidence, evidence, RetrievalMode.HYBRID)
    service._generator = FakeGenerator(sentences)
    service._verifier = FakeVerifier(verdicts)
    return service.answer("톨루엔의 노출기준은?")


class TestTheRefusalSaysWhichHappened:
    def test_all_blocked_is_verification_unavailable(self):
        """msds-03. One sentence, never judged, refused as if it had failed."""
        result = _answer([(SupportVerdict.UNVERIFIED, True)])

        assert result.refusal_reason is RefusalReason.VERIFICATION_UNAVAILABLE
        assert result.quota_blocked == 1

    def test_a_judged_failure_among_them_is_still_unsupported(self):
        """Guards the test above from swallowing real verdicts. One sentence was
        judged and failed, so the answer would have been partial at best."""
        result = _answer(
            [(SupportVerdict.UNSUPPORTED, False), (SupportVerdict.UNVERIFIED, True)]
        )

        assert result.refusal_reason is RefusalReason.ALL_SENTENCES_UNSUPPORTED
        assert result.quota_blocked == 1

    def test_the_outcome_family_does_not_move(self):
        """`AnswerOutcome` is the family, not the reason (BR-127). A new value
        would ripple into the history screen and the refusal metrics; the
        distinction lives in `refusal_reason`."""
        result = _answer([(SupportVerdict.UNVERIFIED, True)])

        assert result.outcome is AnswerOutcome.REFUSED_UNSUPPORTED

    def test_nothing_blocked_keeps_the_old_reason(self):
        result = _answer([(SupportVerdict.UNSUPPORTED, False)])

        assert result.refusal_reason is RefusalReason.ALL_SENTENCES_UNSUPPORTED
        assert result.quota_blocked == 0


class TestTheAnsweredPathCarriesTheCountToo:
    def test_a_partly_blocked_answer_reports_how_many(self):
        """msds-02 and sub-07. The answer came back short and said nothing about
        why - `removed_count` alone reads as "we judged them and they failed"."""
        result = _answer(
            [(SupportVerdict.SUPPORTED, False), (SupportVerdict.UNVERIFIED, True)]
        )

        assert result.outcome is AnswerOutcome.ANSWERED_PARTIAL
        assert result.removed_count == 1
        assert result.quota_blocked == 1

    def test_a_whole_answer_reports_zero(self):
        result = _answer([(SupportVerdict.SUPPORTED, False)])

        assert result.outcome is AnswerOutcome.ANSWERED
        assert result.quota_blocked == 0


# ---- the evaluation ----


class FakeQueryResult:
    def __init__(self, quota_blocked: int) -> None:
        self.query_id = 42
        self.quota_blocked = quota_blocked
        self.outcome = AnswerOutcome.ANSWERED_PARTIAL
        self.sentences = [{"text": "문장."}]
        self.citations = []
        self.retrieved = []


class FakeJudgeLlm:
    """Counts its calls: the blocked item must not reach the judge at all."""

    model = "fake-judge"
    calls = 0

    def generate_structured(self, _prompt, _schema, _system=None):
        FakeJudgeLlm.calls += 1
        return {"correct": True, "faithful": True, "reason": "ok"}, None


class FakeQueryService:
    def __init__(self, quota_blocked: int) -> None:
        self._quota_blocked = quota_blocked
        self.judged = False

    def __call__(self, *_args, **_kwargs):
        return self

    def answer(self, _question, _scope):
        return FakeQueryResult(self._quota_blocked)


def _score_full(monkeypatch, quota_blocked: int):
    """Run `_score_full` with every outside edge replaced.

    No database and no model: the point under test is what the loop does with
    `QueryResult.quota_blocked`, and a test that needed a live quota to
    reproduce a quota failure would never run.
    """
    from app.adapters import embedding_local, llm_factory, tracing
    from app.db import engine
    from app.services import evaluation_service as module

    @contextmanager
    def scope():
        yield FakeSession()

    monkeypatch.setattr(module, "session_scope", scope)
    monkeypatch.setattr(engine, "observability_scope", scope)
    monkeypatch.setattr(embedding_local, "shared_adapter", lambda: object())
    monkeypatch.setattr(tracing, "TracedEmbedding", lambda inner: inner)
    for name in ("build_llm", "build_entity_llm", "build_verify_llm"):
        monkeypatch.setattr(llm_factory, name, lambda *a, **k: object())
    monkeypatch.setattr(llm_factory, "build_judge_llm", lambda *a, **k: FakeJudgeLlm())

    service = FakeQueryService(quota_blocked)
    import app.services.query_service as qs

    monkeypatch.setattr(qs, "QueryService", service)
    monkeypatch.setattr(
        module.EvaluationService, "_calls_for", staticmethod(lambda _qid: 7)
    )

    question = GoldenQuestion(
        id="msds-03",
        category="msds",
        question="톨루엔의 노출기준은?",
        expects=Expects.ANSWER,
    )
    FakeJudgeLlm.calls = 0
    return module.EvaluationService()._score_full(question, {}, 0.0), service


class TestEvaluationRefusesToScoreAnInterruptedItem:
    def test_a_blocked_item_is_quota_exhausted_not_done(self, monkeypatch):
        outcome, _service = _score_full(monkeypatch, quota_blocked=1)

        assert outcome.status is ItemStatus.QUOTA_EXHAUSTED
        assert outcome.error_kind == "verify_quota"

    def test_it_carries_no_metrics_to_average(self, monkeypatch):
        """`reporter.aggregate` reads every rate off `done` items, so an item
        that is not `done` cannot reach a number. These stay unset so that it
        also cannot be read back as a score by anything else."""
        outcome, _service = _score_full(monkeypatch, quota_blocked=1)

        assert outcome.recall_at_5 is None
        assert outcome.reciprocal_rank is None
        assert outcome.citation_precision is None
        assert outcome.refusal_correct is None
        assert outcome.judgement is None

    def test_the_cost_is_still_reported(self, monkeypatch):
        """The calls were spent whether or not the item scored."""
        outcome, _service = _score_full(monkeypatch, quota_blocked=1)

        assert outcome.llm_calls == 7

    def test_the_judge_is_not_spent_on_a_truncated_answer(self, monkeypatch):
        """The judge runs on its own daily quota (BR-122), and the sentence set
        it would grade is not the one the product would have produced."""
        _outcome, _service = _score_full(monkeypatch, quota_blocked=1)

        assert FakeJudgeLlm.calls == 0

    def test_an_unblocked_item_is_scored_normally(self, monkeypatch):
        outcome, _service = _score_full(monkeypatch, quota_blocked=0)

        assert outcome.status is ItemStatus.DONE


class TestTheRunDoesNotEndSucceeded:
    def test_a_blocked_item_sets_quota_hit_and_the_loop_continues(self):
        """The `QuotaExhaustedError` branch breaks; this one does not.

        There the answer could not be produced at all, so the next question
        fails the same way. Here the query completed and only some verification
        calls were turned away - run 609's msds-02 had 5 blocked against 8 that
        succeeded inside one query, which is a per-minute limit, not a spent
        day. A `--full` run costs days of judge quota and must not be abandoned
        over a condition that clears in a minute; if the day really is gone, the
        answer call raises and the existing `break` still ends the run.
        """
        from app.evaluation.types import GoldenSet, ItemOutcome, RunMode
        from app.services.evaluation_service import EvaluationService

        questions = tuple(
            GoldenQuestion(
                id=f"q-{i}", category="msds", question="질문", expects=Expects.ANSWER
            )
            for i in range(3)
        )
        golden = GoldenSet(path="x", sha256="y", questions=questions)
        seen: list[str] = []
        finished: dict = {}

        class Loop(EvaluationService):
            def _score(self, question, resolve, mode):
                seen.append(question.id)
                return ItemOutcome(
                    question_id=question.id,
                    category=question.category,
                    expects=question.expects,
                    status=(
                        ItemStatus.QUOTA_EXHAUSTED
                        if question.id == "q-0"
                        else ItemStatus.DONE
                    ),
                )

            def _store(self, run_id, outcome):
                finished.setdefault("stored", []).append(outcome)

            def _finish(self, run_id, mode, quota_hit):
                finished["quota_hit"] = quota_hit
                return quota_hit

        result = Loop()._execute(1, golden, {}, RunMode.FULL, already_scored=set())

        assert seen == ["q-0", "q-1", "q-2"], "한 문항의 중단이 실행을 끝내면 안 됩니다"
        assert finished["quota_hit"] is True
        assert result is True
        assert [o.status for o in finished["stored"]][0] is ItemStatus.QUOTA_EXHAUSTED


class TestResumeSolvesTheBlockedItemAgain:
    def test_scored_question_ids_excludes_quota_exhausted(self):
        """D. A resume must re-run what was interrupted, or the item stays
        unmeasured for the life of the run and the run can never leave
        `partial`. Read off the statement rather than a database: the filter is
        the fact under test."""
        from app.db.repositories.evaluation import EvaluationRepo

        captured: list = []

        class CapturingSession:
            def scalars(self, statement):
                captured.append(statement)
                return []

        EvaluationRepo(CapturingSession()).scored_question_ids(1)
        sql = str(
            captured[0].compile(compile_kwargs={"literal_binds": True})
        )

        assert "'done'" in sql
        assert "quota_exhausted" not in sql
        assert "'failed'" not in sql
