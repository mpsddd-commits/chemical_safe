"""Observability outlives the work it observes — BR-78, BR-95.

Measured 2026-08-25: three queries failed on a provider 429 and left **no**
`query_log` rows and **no** `llm_call` rows. `session_scope` rolls the whole
transaction back on an exception, so the record that a query was attempted
vanished together with the attempt.

That is the same shape as defect 26 (BR-72): a rule that reads correctly and
cannot hold given the transaction structure. BR-78 says a refusal is recorded
rather than counted as an error, and BR-95 says failed calls are recorded too —
neither is reachable on the error path if the error erases the record.

The split: **answer content** is all-or-nothing (BR-92), **the fact that we
tried** survives anything.
"""

from __future__ import annotations

import pytest

from app.core.types import AnswerOutcome, RetrievalMode
from app.db.repositories.queries import QueryRepo


class FakeSession:
    """Records what was added, flushed and committed. No database."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.added: list = []
        self.commits = 0
        self.rollbacks = 0
        self._next_id = 1

    def add(self, obj) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            try:
                obj.id = self._next_id
                self._next_id += 1
            except Exception:  # noqa: BLE001 - some rows have composite keys
                pass

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class TestSessionSplit:
    def test_log_row_goes_to_the_log_session(self):
        content, log = FakeSession("content"), FakeSession("log")
        repo = QueryRepo(content, log)
        repo.start("황산 보호구는?", RetrievalMode.HYBRID)

        assert len(log.added) == 1
        assert content.added == []

    def test_commit_log_commits_only_the_log_session(self):
        """The answer content must not be committed early — that would defeat BR-92."""
        content, log = FakeSession("content"), FakeSession("log")
        repo = QueryRepo(content, log)
        repo.start("q", RetrievalMode.HYBRID)
        repo.commit_log()

        assert log.commits == 1
        assert content.commits == 0

    def test_shared_session_never_commits(self):
        """With one session (tests, read-only callers) committing early would
        commit the answer content too, so `commit_log` deliberately does nothing."""
        shared = FakeSession("shared")
        repo = QueryRepo(shared)
        repo.start("q", RetrievalMode.HYBRID)
        repo.commit_log()

        assert shared.commits == 0

    def test_commit_failure_rolls_back_and_does_not_raise(self):
        """Observability must never mask the real failure it is recording."""
        content = FakeSession("content")

        class Broken(FakeSession):
            def commit(self) -> None:
                raise RuntimeError("log db down")

        log = Broken("log")
        repo = QueryRepo(content, log)
        repo.start("q", RetrievalMode.HYBRID)
        repo.commit_log()  # must not raise

        assert log.rollbacks == 1


class TestOutcomeRecording:
    def _row(self):
        content, log = FakeSession("content"), FakeSession("log")
        repo = QueryRepo(content, log)
        return repo, repo.start("q", RetrievalMode.HYBRID), log

    def test_a_started_query_defaults_to_error(self):
        """An unfinished query is a failed one, not a successful one."""
        _repo, row, _log = self._row()
        assert row.outcome == AnswerOutcome.ERROR.value

    def test_mark_error_records_timing(self):
        repo, row, _log = self._row()
        repo.mark_error(row, total_ms=1234)
        assert row.outcome == AnswerOutcome.ERROR.value
        assert row.total_ms == 1234

    def test_refusal_is_not_an_error(self):
        """BR-78 — a refusal is an outcome with a reason, not a failure."""
        from app.core.types import RefusalReason

        repo, row, _log = self._row()
        repo.refuse(row, RefusalReason.BELOW_THRESHOLD, total_ms=50)
        assert row.outcome == AnswerOutcome.REFUSED_LOW_RELEVANCE.value
        assert row.refusal_reason == RefusalReason.BELOW_THRESHOLD.value

    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("below_threshold", AnswerOutcome.REFUSED_LOW_RELEVANCE.value),
            ("no_candidates", AnswerOutcome.REFUSED_LOW_RELEVANCE.value),
            ("all_sentences_unsupported", AnswerOutcome.REFUSED_UNSUPPORTED.value),
        ],
    )
    def test_refusal_reasons_map_to_outcomes(self, reason, expected):
        from app.core.types import RefusalReason

        repo, row, _log = self._row()
        repo.refuse(row, RefusalReason(reason), total_ms=1)
        assert row.outcome == expected
