"""Persistence and failure isolation against a live PostgreSQL.

Every behaviour checked here passed its unit test and still broke in the real
system — defects 26 (BR-72 unreachable through a shared session), 31
(observability rolled back with the work it observed), 38 (a thread race that
looked like an evidence problem). A mocked session cannot show any of them,
because in each case the mock *was* the thing being got wrong.
"""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import func, select

from app.core.types import RefusalReason, RetrievalMode, SupportVerdict
from app.db.engine import observability_scope, session_scope
from app.db.models import (
    AnswerCitationRow,
    AnswerSentenceRow,
    ChunkRow,
    CitationSnapshotRow,
    LlmCallRow,
    QueryLogRow,
)
from app.db.repositories.queries import CitationDraft, QueryRepo, SentenceDraft

pytestmark = pytest.mark.integration


def _drafts(chunk_id: int) -> list[SentenceDraft]:
    return [
        SentenceDraft(
            ordinal=0,
            text="방진마스크를 착용해야 합니다.",
            support=SupportVerdict.SUPPORTED,
            removed=False,
            citations=[
                CitationDraft(
                    chunk_id=chunk_id,
                    rank=0,
                    document_id=1,
                    source_url="https://example.test/d",
                    document_title="테스트 문서",
                    section_code="msds_08",
                    section_title="노출방지 및 개인보호구",
                    snippet="방진마스크를 착용한다.",
                    start_offset=0,
                    end_offset=12,
                )
            ],
        )
    ]


@pytest.fixture
def live_chunk_id() -> int:
    """A real chunk to cite. The FK is the point of these tests."""
    with session_scope() as session:
        chunk_id = session.scalar(select(ChunkRow.id).limit(1))
    assert chunk_id, "corpus is empty - run an ingest first"
    return chunk_id


@pytest.fixture
def disposable_chunk_id():
    """A chunk that exists **only** for the test that deletes it.

    The deletion test used to take the first row of the real corpus and delete
    it for good, so every run of this suite left the corpus one chunk and one
    vector lighter than it found it - measured, 1,649 -> 1,648 across a single
    run, with nothing reporting it. A test that erodes the data it is verifying
    is not a test of that data.

    Ordinal is pushed past the document's own chunks so `replace_for_document`
    ordering is untouched if this row somehow outlives the test.
    """
    with session_scope() as session:
        document_id = session.scalar(select(ChunkRow.document_id).limit(1))
        assert document_id, "corpus is empty - run an ingest first"
        next_ordinal = session.scalar(
            select(func.max(ChunkRow.ordinal)).where(ChunkRow.document_id == document_id)
        )
        chunk = ChunkRow(
            document_id=document_id,
            section_id=None,
            ordinal=(next_ordinal or 0) + 1000,
            text="통합 테스트 전용 청크",
            token_count=8,
            start_offset=0,
            end_offset=1,
            meta={},
        )
        session.add(chunk)
        session.flush()
        chunk_id = chunk.id

    yield chunk_id

    # The test deletes it; this is the safety net for a failure before that.
    with session_scope() as session:
        leftover = session.get(ChunkRow, chunk_id)
        if leftover is not None:
            session.delete(leftover)


class TestObservabilitySurvivesRollback:
    """Defect 31 — the record that a query ran must outlive the query."""

    def test_log_row_and_traces_survive_a_rolled_back_content_session(self):
        with observability_scope() as obs:
            with pytest.raises(RuntimeError):
                with session_scope() as content:
                    repo = QueryRepo(content, obs)
                    row = repo.start("롤백 검증 질의", RetrievalMode.HYBRID)
                    repo.commit_log()
                    query_id = row.id

                    LlmCallRepoRow = LlmCallRow(
                        query_id=query_id,
                        purpose="answer",
                        provider="test",
                        model="test-model",
                        latency_ms=10,
                        ok=False,
                        error_kind="Injected",
                    )
                    obs.add(LlmCallRepoRow)
                    obs.flush()

                    # Content written, then the transaction dies.
                    for draft in _drafts(1):
                        content.add(
                            AnswerSentenceRow(
                                query_id=query_id,
                                ordinal=draft.ordinal,
                                text=draft.text,
                                support=draft.support.value,
                                removed=draft.removed,
                            )
                        )
                    content.flush()
                    raise RuntimeError("injected failure")

        with session_scope() as check:
            assert check.get(QueryLogRow, query_id) is not None, "log row was rolled back"
            traces = check.scalar(
                select(func.count()).select_from(LlmCallRow).where(
                    LlmCallRow.query_id == query_id
                )
            )
            sentences = check.scalar(
                select(func.count()).select_from(AnswerSentenceRow).where(
                    AnswerSentenceRow.query_id == query_id
                )
            )
        assert traces == 1, "llm_call rows were rolled back with the content"
        assert sentences == 0, "answer content survived a failure - BR-92 broken"


class TestAnswerContentIsAtomic:
    """BR-92 — sentences, citations and snapshots commit together or not at all."""

    def test_a_failure_after_the_sentence_leaves_nothing(self, live_chunk_id):
        with observability_scope() as obs:
            with session_scope() as content:
                repo = QueryRepo(content, obs)
                row = repo.start("원자성 검증", RetrievalMode.HYBRID)
                repo.commit_log()
                query_id = row.id

            with pytest.raises(RuntimeError):
                with session_scope() as content:
                    repo = QueryRepo(content, obs)
                    log_row = content.get(QueryLogRow, query_id)
                    repo.finalise(
                        log_row,
                        _drafts(live_chunk_id),
                        outcome=__import__(
                            "app.core.types", fromlist=["AnswerOutcome"]
                        ).AnswerOutcome.ANSWERED,
                        total_ms=100,
                    )
                    raise RuntimeError("injected after finalise, before commit")

        with session_scope() as check:
            sentences = check.scalar(
                select(func.count()).select_from(AnswerSentenceRow).where(
                    AnswerSentenceRow.query_id == query_id
                )
            )
        assert sentences == 0

    def test_no_citation_exists_without_its_snapshot(self):
        """The invariant, checked across everything the system has ever written."""
        with session_scope() as session:
            orphans = session.scalar(
                select(func.count())
                .select_from(AnswerCitationRow)
                .outerjoin(
                    CitationSnapshotRow,
                    CitationSnapshotRow.citation_id == AnswerCitationRow.id,
                )
                .where(CitationSnapshotRow.citation_id.is_(None))
            )
        assert orphans == 0


class TestReindexDoesNotBlockOnCitations:
    """E16 SET NULL — the defect the FD review caught before it shipped.

    RESTRICT would have made any document that was ever cited permanently
    un-reindexable, and re-indexing is how every parsing-rule change ships here
    (BR-20a, BR-31a, BR-27a).
    """

    def test_deleting_a_cited_chunk_nulls_the_link_and_keeps_the_snapshot(
        self, disposable_chunk_id
    ):
        from app.core.types import AnswerOutcome

        with observability_scope() as obs, session_scope() as content:
            repo = QueryRepo(content, obs)
            row = repo.start("재색인 검증", RetrievalMode.HYBRID)
            repo.commit_log()
            repo.finalise(
                row,
                _drafts(disposable_chunk_id),
                outcome=AnswerOutcome.ANSWERED,
                total_ms=1,
            )
            content.flush()
            citation_id = content.scalar(
                select(AnswerCitationRow.id)
                .join(AnswerSentenceRow, AnswerSentenceRow.id == AnswerCitationRow.sentence_id)
                .where(AnswerSentenceRow.query_id == row.id)
            )
            repo.commit_log()

        # Simulate what BR-54 re-indexing does to that chunk.
        with session_scope() as session:
            chunk = session.get(ChunkRow, disposable_chunk_id)
            snapshot_before = session.get(CitationSnapshotRow, citation_id)
            assert snapshot_before is not None
            session.delete(chunk)

        with session_scope() as check:
            citation = check.get(AnswerCitationRow, citation_id)
            snapshot = check.get(CitationSnapshotRow, citation_id)
        assert citation is not None, "the citation was deleted - CASCADE, not SET NULL"
        assert citation.chunk_id is None, "the link should be released, not held"
        assert snapshot is not None and snapshot.snippet, "the evidence must survive"


class TestRetrievalRouteIsolation:
    """Defect 26 — one failing route must not take the other down.

    A shared Session leaves PostgreSQL in `InFailedSqlTransaction` after a bad
    statement, so without a savepoint the second route fails with a message
    about the first one's aborted transaction.
    """

    def test_a_broken_route_leaves_the_session_usable(self):
        from sqlalchemy import text

        from app.adapters.embedding_local import DeterministicEmbeddingAdapter
        from app.rag.retrieval.retrievers import Retrievers

        with session_scope() as session:
            retrievers = Retrievers(session, DeterministicEmbeddingAdapter())

            def explode():
                session.execute(text("SELECT no_such_function()"))

            result = retrievers._isolated("broken", explode)
            assert result.failed is True

            # The session must still work - this is what defect 26 broke.
            alive = session.scalar(select(func.count()).select_from(ChunkRow))
            assert alive and alive > 0


class TestConcurrentAdapterClient:
    """Defect 38 — the client is built lazily from a thread pool (PP-5)."""

    def test_parallel_first_use_yields_one_client(self):
        pytest.importorskip("google.genai", reason="google-genai not installed here")

        from app.adapters.llm_gemini import GeminiLLMAdapter
        from app.core.config import get_settings

        settings = get_settings()
        if not settings.gemini_api_key.get_secret_value():
            pytest.skip("no GEMINI_API_KEY")

        adapter = GeminiLLMAdapter(settings)
        seen: list[object] = []
        barrier = threading.Barrier(8)

        def grab():
            barrier.wait()
            seen.append(adapter._get_client())

        threads = [threading.Thread(target=grab) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len({id(c) for c in seen}) == 1, "the lazy init raced"


class TestRefusalIsRecorded:
    """BR-78 — a refusal is an outcome with a reason, not an error."""

    def test_refusal_persists_with_its_reason(self):
        with observability_scope() as obs, session_scope() as content:
            repo = QueryRepo(content, obs)
            row = repo.start("거부 기록 검증", RetrievalMode.HYBRID)
            repo.refuse(row, RefusalReason.BELOW_THRESHOLD, total_ms=42)
            repo.commit_log()
            query_id = row.id

        with session_scope() as check:
            stored = check.get(QueryLogRow, query_id)
        assert stored.outcome == "refused_low_relevance"
        assert stored.refusal_reason == "below_threshold"
        assert stored.total_ms == 42
