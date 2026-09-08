"""S3 QueryService - workflows W7, W8 and W9.

Stateless (FR-22): no session, no history, nothing carried between questions.

The shape of this class is the failure policy. Retrieval degrades - one route
down, reranker down, fewer candidates - and the query proceeds on what is left
(BR-71, BR-72). Grounding does not degrade: a sentence that cannot be verified
is removed (BR-87), and if persistence of the answer's evidence fails, the whole
answer is rolled back (BR-92). Evidence quality is the one thing this system
will not trade for availability.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.adapters.llm_trace import CallContext, TracedLlm
from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError
from app.core.logging import get_logger
from app.core.types import (
    AnswerOutcome,
    LlmPurpose,
    RefusalReason,
    RetrievalMode,
    Scope,
    SupportVerdict,
)
from app.db.repositories.queries import QueryRepo, SentenceDraft
from app.db.repositories.traces import LlmCallRepo
from app.indexing.keyword_index import EXACT_MATCH_SCORE
from app.processing.stages.normalize import normalize
from app.rag import refusal
from app.rag.assembler import PromptAssembler
from app.rag.citations import resolve_evidence, to_citation_draft
from app.rag.entities import EntityExtractor
from app.rag.generator import AnswerGenerator
from app.rag.retrieval.fusion import (
    ensure_doc_type_spread,
    ensure_subject_presence,
    reciprocal_rank_fusion,
)
from app.rag.retrieval.rerank_client import RerankClient, evidence_texts
from app.rag.retrieval.retrievers import Retrievers
from app.rag.types import Evidence, RetrievalCandidate
from app.rag.verifier import SupportVerifier

log = get_logger(__name__)

EventSink = Callable[[str, dict], None]


def observation_window(
    head: list[RetrievalCandidate],
    fused: list[RetrievalCandidate],
    depth: int,
) -> list[RetrievalCandidate]:
    """C4(b) - widen what evaluation observes without widening what the answer uses.

    `head` is returned first and untouched. That is the whole design, and it is
    load-bearing: Recall@5 is read off the first five positions, so anything
    that reorders them changes the number it is supposed to hold still.
    Measured 2026-09-06 (runs 550 and 551): raising `FINAL_TOP_K` to 10 rebuilt
    the head through `ensure_doc_type_spread` and moved Recall@5 from 0.967 to
    0.933 - sub-02 gained, sub-06 and sub-07 lost. Appending cannot do that.

    The tail is the fused candidates this same call already ranked and then
    dropped, in fused order, skipping whatever the head lifted out of order
    (BR-65a and BR-69 both promote from below, so overlap is normal, and a
    chunk appearing twice would be counted twice by Recall@10).

    Nothing is retrieved a second time. `depth` under `len(head)` truncates
    nothing: the head is not negotiable.
    """
    seen = {c.chunk_id for c in head}
    window = list(head)
    for candidate in fused:
        if len(window) >= depth:
            break
        if candidate.chunk_id in seen:
            continue
        seen.add(candidate.chunk_id)
        window.append(candidate)
    return window


def retrieved_refs(evidence) -> list[dict]:
    """Project the candidate list onto what evaluation compares (u4).

    Ranks 0 to `final_top_k - 1` are the positions the pipeline actually used,
    so Recall@5 and MRR are computed against the same ordering the answer saw.
    Ranks below that are the observation tail (C4(b), `observation_top_k`):
    real fused positions from this same call, which the answer did *not* read.
    Recall@10 therefore asks "did retrieval find it at all", and Recall@5 asks
    "did ranking put it where the answer could use it" - two different
    questions, which is what BR-124 wanted from the pair.

    `section_code` is `None` for chunks whose sections were folded by BR-31a -
    that is a fact about the corpus, and u4 scores those documents at document
    level rather than treating them as always-missed.
    """
    return [
        {
            "rank": rank,
            "chunk_id": item.chunk_id,
            "document_id": item.document_id,
            "section_code": item.section_code,
        }
        for rank, item in enumerate(evidence)
    ]


@dataclass
class QueryResult:
    query_id: int
    outcome: AnswerOutcome
    sentences: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    refusal_reason: RefusalReason | None = None
    links: list[dict] = field(default_factory=list)
    removed_count: int = 0
    # The ordered candidate list, head first (C4(b)). u2 has no use for it; u4
    # does, and the alternative was for the evaluator to run retrieval a second
    # time - which would score a *different* execution than the one that
    # produced the answer. DD-22 asks the evaluation to observe the real path,
    # so the real path hands out what it saw.
    #
    # This field is observation-only and always has been: the consumers are
    # `evaluation_service` and `reporter`, and it is not written to `query_log`
    # (checked 2026-09-07). So widening it past `final_top_k` is not the
    # evaluation-only retrieval path BR-115 forbids - it is the same window,
    # opened wider. The answer, the citations and the refusal are still decided
    # by the head alone, and the product behaviour is byte-identical; the guard
    # on that claim is Recall@5, which must stay at 0.967.
    retrieved: list[dict] = field(default_factory=list)
    retrieval_ms: int = 0
    total_ms: int = 0
    mode: RetrievalMode = RetrievalMode.HYBRID


class QueryService:
    def __init__(
        self,
        session: Session,
        llm,
        embedder,
        settings: Settings | None = None,
        entity_llm=None,
        verify_llm=None,
        obs_session: Session | None = None,
    ) -> None:
        """`entity_llm` is separate on purpose (BR-64).

        Entity extraction runs inside the NFR-2 retrieval budget and only
        improves ranking, so it is given a client with no retries and a short
        timeout. Passing the same object for both is fine in tests; in the app
        the routers hand in `build_entity_llm()`.
        """
        self._s = session
        self._settings = settings or get_settings()
        # Observability is written on its own transaction so a failed query
        # still leaves a `query_log` row and its `llm_call` rows behind. BR-92's
        # all-or-nothing applies to the *answer content*, not to the record that
        # we tried. See `db/repositories/queries.py`.
        log_session = obs_session if obs_session is not None else session
        self._repo = QueryRepo(session, log_session)
        self._retrievers = Retrievers(session, embedder, self._settings)
        self._reranker = RerankClient(self._settings)
        assembler = PromptAssembler(settings=self._settings)

        # FR-41 / BR-95 - every call is wrapped, so a call cannot be made
        # without a `llm_call` row. `purpose` is fixed per wrapper because that
        # is what keeps `verify` cost from hiding inside `answer` (BR-86a).
        traces = LlmCallRepo(log_session)
        self._context = CallContext()
        provider = self._settings.llm_provider

        def traced(inner, purpose: LlmPurpose):
            return TracedLlm(inner, traces, purpose, self._context, provider)

        self._entities = EntityExtractor(
            session,
            traced(entity_llm if entity_llm is not None else llm, LlmPurpose.ENTITY),
            assembler,
            self._settings,
        )
        self._generator = AnswerGenerator(traced(llm, LlmPurpose.ANSWER), assembler)
        # A separate client on purpose - see `build_verify_llm`. Falls back to
        # the main one so tests and simple callers need not care.
        self._verifier = SupportVerifier(
            traced(verify_llm if verify_llm is not None else llm, LlmPurpose.VERIFY),
            assembler,
            self._settings,
        )

    # ---- W7 ----
    def retrieve(
        self, question: str, scope: Scope
    ) -> tuple[list[Evidence], list[Evidence], RetrievalMode]:
        """Returns (head, observed, mode).

        `head` is what the answer is built from - `final_top_k` items, exactly
        as before. `observed` is the same head followed by the fused tail that
        only evaluation reads (C4(b)); it is returned separately rather than
        appended to `head` so that no caller can pass the wide list to the
        generator by accident.
        """
        normalised = normalize(question)
        intent = self._entities.extract(normalised)

        keyword = self._retrievers.keyword(normalised, intent, scope)
        vector = self._retrievers.vector(normalised, intent, scope)
        if keyword.failed and vector.failed:
            # BR-72 - one route down is degradation; both down is a real error.
            raise RuntimeError("both retrieval routes failed")

        chunk_ids = [c.chunk_id for c in keyword.candidates + vector.candidates]
        doc_types, document_ids = self._retrievers.chunk_metadata(chunk_ids)

        fused = reciprocal_rank_fusion(
            keyword.candidates,
            vector.candidates,
            k=self._settings.rrf_k,
            doc_types=doc_types,
            document_ids=document_ids,
        )[: self._settings.fusion_top_k]
        spread = ensure_doc_type_spread(fused, self._settings.final_top_k)
        # BR-65a - a substance the user named (typed CAS or resolved name) must
        # be represented in the head. Exact hits carry the EXACT_MATCH_SCORE
        # marker, which is what BR-38 put it there for.
        subject_ids = {
            c.chunk_id
            for c in keyword.candidates
            if c.score >= EXACT_MATCH_SCORE
        }
        spread = ensure_subject_presence(spread, fused, subject_ids)

        # One query for head and tail together, then split by id. Resolving the
        # tail separately would add a round trip inside the NFR-2 budget for
        # something only evaluation reads, and the head must not pay for the
        # observation. Splitting by id rather than by position because
        # `resolve_evidence` drops chunks a re-index removed mid-query.
        head_ids = {c.chunk_id for c in spread}
        window = observation_window(spread, fused, self._settings.observation_top_k)
        resolved = resolve_evidence(self._s, window)
        evidence = [e for e in resolved if e.chunk_id in head_ids]
        tail = [e for e in resolved if e.chunk_id not in head_ids]

        mode = RetrievalMode.HYBRID
        if self._reranker.enabled and evidence:
            reordered, reranked = self._reranker.rerank(
                normalised, spread, evidence_texts(evidence)
            )
            if reranked:
                mode = RetrievalMode.HYBRID_RERANKED
                evidence = resolve_evidence(self._s, reordered)
        # Rebuilt from `evidence` so the observed head reflects the reranked
        # order the answer actually saw, not the pre-rerank one.
        return evidence, evidence + tail, mode

    # ---- W7 + W8 + W9 ----
    def answer(
        self, question: str, scope: Scope | None = None, emit: EventSink | None = None
    ) -> QueryResult:
        scope = scope or Scope(owner_id=None)
        emit = emit or (lambda _event, _data: None)
        started = time.perf_counter()

        question = question[: self._settings.query_max_chars]  # SP-7
        row = self._repo.start(question, RetrievalMode.HYBRID)
        # Committed before retrieval so the row survives whatever happens next,
        # and so `answer_sentence.query_id` has something to reference when the
        # content transaction commits later.
        self._repo.commit_log()
        # From here every traced call carries the query id (E18.query_id).
        self._context.query_id = row.id

        try:
            return self._answer(question, scope, emit, row, started)
        except Exception:
            # BR-78 / BR-95 - the attempt is recorded even though it failed.
            # Without this the row and its `llm_call` rows roll back with the
            # content session and the failure leaves no trace at all.
            self._repo.mark_error(row, total_ms=int((time.perf_counter() - started) * 1000))
            self._repo.commit_log()
            raise

    def _answer(
        self,
        question: str,
        scope: Scope,
        emit: EventSink,
        row,
        started: float,
    ) -> QueryResult:
        """The body of `answer`, split out so the error path has one place.

        Everything here may raise; `answer` records the attempt either way.
        """
        retrieval_started = time.perf_counter()
        evidence, observed, mode = self.retrieve(question, scope)
        retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)
        row.mode = mode.value
        # The relevance the refusal actually judged on, not the fused rank score.
        # Logging a different number than the one that decided makes the
        # threshold impossible to calibrate from the log (BR-73, BR-74).
        top_score = max(
            (e.relevance for e in evidence if e.relevance is not None), default=None
        )
        self._repo.record_retrieval(
            row, candidate_count=len(evidence), top_score=top_score, ms=retrieval_ms
        )
        emit("retrieval", {"count": len(evidence), "ms": retrieval_ms})
        # The wide list, not `evidence` - everything downstream of here still
        # reads `evidence` and only `evidence`.
        retrieved = retrieved_refs(observed)

        # ---- stage one refusal (BR-73) - no LLM call happens past here ----
        decision = refusal.decide(evidence, self._settings)
        if decision.refused:
            total_ms = int((time.perf_counter() - started) * 1000)
            self._repo.refuse(row, decision.reason, total_ms=total_ms)
            self._repo.commit_log()
            emit("refused", {"reason": decision.reason.value, "links": decision.links})
            return QueryResult(
                query_id=row.id,
                outcome=AnswerOutcome(row.outcome),
                refusal_reason=decision.reason,
                links=decision.links,
                retrieved=retrieved,
                retrieval_ms=retrieval_ms,
                total_ms=total_ms,
                mode=mode,
            )

        # ---- generation ----
        # Deltas are provisional: not yet whitelisted (SP-8), not yet verified
        # (BR-85~87). The client shows them without citation badges until
        # `final` arrives (FE-16).
        def on_delta(index: int, text: str) -> None:
            emit("token", {"sentence": index, "text": text})

        try:
            generated = self._generator.generate(question, evidence, on_delta)
        except ConfigurationError:
            # BR-02 - no API key. The app is up; querying is not available.
            raise

        if generated.refused:
            total_ms = int((time.perf_counter() - started) * 1000)
            self._repo.refuse(row, RefusalReason.PROVIDER_REFUSAL, total_ms=total_ms)
            self._repo.commit_log()
            emit(
                "refused",
                {
                    "reason": RefusalReason.PROVIDER_REFUSAL.value,
                    "links": refusal.source_links(evidence),
                },
            )
            return QueryResult(
                query_id=row.id,
                outcome=AnswerOutcome.REFUSED_LOW_RELEVANCE,
                refusal_reason=RefusalReason.PROVIDER_REFUSAL,
                links=refusal.source_links(evidence),
                retrieved=retrieved,
                retrieval_ms=retrieval_ms,
                total_ms=total_ms,
                mode=mode,
            )

        # ---- stage two verification (BR-85~87) ----
        emit("verifying", {"sentences": len(generated.sentences)})
        by_id = {item.chunk_id: item for item in evidence}
        verified = self._verifier.verify_all(generated.sentences, by_id)
        kept = [v for v in verified if v.kept]
        removed = len(verified) - len(kept)
        # Removed because we could not ask, not because the answer failed.
        quota_blocked = sum(1 for v in verified if v.unverified_by_quota)

        if not kept:
            # BR-76 - nothing survived verification, so this is a refusal, not
            # an empty answer.
            total_ms = int((time.perf_counter() - started) * 1000)
            if not verified:
                # "The generator produced nothing" and "everything it produced
                # was filtered out" both arrive here and both get recorded as
                # `all_sentences_unsupported`, which names only the second one.
                # They have different causes and different fixes, so they are
                # separated in the log rather than in `RefusalReason`: a new
                # reason would ripple into the screen text, the repository's
                # outcome mapping and the evaluation verdicts, and baseline 609
                # was promoted against the reasons as they stand.
                log.warning(
                    "empty_generation",
                    extra={
                        "query_id": row.id,
                        "evidence_count": len(evidence),
                        "question_chars": len(question),
                    },
                )
            # Every filtered sentence is stored with its own verdict, the same
            # way the answered path stores what it dropped (BR-88, see below).
            # Until 2026-09-08 this path stored none: run 609's refusals
            # (`query_log` 448, 450, 462) each left zero `answer_sentence` rows
            # while returning `removed_count`, so the BR-88 comment forty lines
            # down - "a count with no rows behind it cannot be audited" - was
            # being broken by the branch that refuses. It cost us the only
            # available diagnosis when msds-03 and sub-04 refused in run 609 and
            # then answered in all three reproductions five minutes later, same
            # code, same corpus, temperature 0.
            #
            # This adds observation only. The outcome, the refusal reason and
            # the links are unchanged, and `QueryResult` below carries no
            # sentences either way, so nothing the user sees moves.
            removed_drafts = [
                SentenceDraft(
                    ordinal=ordinal,
                    text=item.sentence.text,
                    support=item.verdict,
                    removed=True,
                    citations=[],
                )
                for ordinal, item in enumerate(verified)
            ]
            self._repo.refuse(
                row,
                RefusalReason.ALL_SENTENCES_UNSUPPORTED,
                total_ms=total_ms,
                sentences=removed_drafts,
            )
            self._repo.commit_log()
            emit(
                "refused",
                {
                    "reason": RefusalReason.ALL_SENTENCES_UNSUPPORTED.value,
                    "links": refusal.source_links(evidence),
                    "quota_blocked": quota_blocked,
                },
            )
            return QueryResult(
                query_id=row.id,
                outcome=AnswerOutcome.REFUSED_UNSUPPORTED,
                refusal_reason=RefusalReason.ALL_SENTENCES_UNSUPPORTED,
                links=refusal.source_links(evidence),
                removed_count=removed,
                retrieved=retrieved,
                retrieval_ms=retrieval_ms,
                total_ms=total_ms,
                mode=mode,
            )

        outcome = (
            AnswerOutcome.ANSWERED_PARTIAL if removed else AnswerOutcome.ANSWERED
        )
        drafts: list[SentenceDraft] = []
        citations: list[dict] = []
        for ordinal, item in enumerate(kept):
            cites = [
                to_citation_draft(by_id[cid], rank)
                for rank, cid in enumerate(item.sentence.chunk_ids)
                if cid in by_id
            ]
            drafts.append(
                SentenceDraft(
                    ordinal=ordinal,
                    text=item.sentence.text,
                    support=SupportVerdict.SUPPORTED,
                    removed=False,
                    citations=cites,
                )
            )
            citations.extend(
                {
                    "sentence_ordinal": ordinal,
                    "rank": c.rank,
                    "chunk_id": c.chunk_id,
                    "title": c.document_title,
                    "section_code": c.section_code,
                    "snippet": c.snippet,
                    "source_url": c.source_url,
                }
                for c in cites
            )

        # Removed sentences are stored too (BR-88): the screen states how many
        # were dropped, and a count with no rows behind it cannot be audited.
        for offset, item in enumerate((v for v in verified if not v.kept), start=len(kept)):
            drafts.append(
                SentenceDraft(
                    ordinal=offset,
                    text=item.sentence.text,
                    support=item.verdict,
                    removed=True,
                    citations=[],
                )
            )

        total_ms = int((time.perf_counter() - started) * 1000)
        # BR-92 - sentences, citations and snapshots commit together or not at
        # all. A failure here rolls the answer back rather than returning one
        # whose evidence cannot be shown.
        self._repo.finalise(row, drafts, outcome=outcome, total_ms=total_ms)
        # The outcome and the traces; the content commits with `session_scope`.
        self._repo.commit_log()

        result = QueryResult(
            query_id=row.id,
            outcome=outcome,
            sentences=[
                {"ordinal": i, "text": v.sentence.text, "chunk_ids": v.sentence.chunk_ids}
                for i, v in enumerate(kept)
            ],
            citations=citations,
            removed_count=removed,
            retrieved=retrieved,
            retrieval_ms=retrieval_ms,
            total_ms=total_ms,
            mode=mode,
        )
        emit(
            "final",
            {
                "outcome": outcome.value,
                "query_id": row.id,
                "sentences": result.sentences,
                "citations": citations,
                "removed": removed,
                "quota_blocked": quota_blocked,
            },
        )
        return result
