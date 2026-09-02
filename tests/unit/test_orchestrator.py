"""Ingestion orchestration — BR-01 ~ BR-08, BR-40 ~ BR-45.

The behaviour under test is the one that decides whether a thousand-document run
is usable: one bad document must not cost the other 999.

Everything is stubbed. `IngestionOrchestrator` takes its collaborators as
arguments precisely so this is possible without a database or a network
(DD-20, NFR-28).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.core.errors import (
    ExtractionError,
    FailureKind,
    SourceUnavailableError,
)
from app.core.types import JobKind, PolicyDecision, RawDocument, SourceRef
from app.ingestion.change_detector import ChangeDetector
from app.ingestion.orchestrator import IngestionOrchestrator
from app.ingestion.policy import PolicyVerdict
from app.jobs.tracker import JobTracker
from tests.unit.test_job_tracker import FakeJobRepo


@dataclass
class StubPolicy:
    blocked_urls: frozenset[str] = frozenset()

    def check(self, url: str) -> PolicyVerdict:
        if url in self.blocked_urls:
            return PolicyVerdict(PolicyDecision.BLOCKED, "robots disallow", datetime.now(UTC))
        return PolicyVerdict(PolicyDecision.ALLOWED, "ok", datetime.now(UTC))

    def is_allowed(self, url: str) -> bool:
        return url not in self.blocked_urls


class StubAdapter:
    def __init__(self, refs: list[SourceRef], failures: dict[str, Exception] | None = None):
        self._refs = refs
        self._failures = failures or {}
        self.fetch_calls: list[str] = []

    def source_id(self) -> str:
        return "stub"

    def list_targets(self, since):
        return iter(self._refs)

    def fetch(self, ref: SourceRef) -> RawDocument:
        self.fetch_calls.append(ref.ref_key)
        error = self._failures.get(ref.ref_key)
        if error is not None:
            # Transient stubs are exhausted after the configured attempts so a
            # retry test can also assert eventual success.
            if isinstance(error, list):
                if error:
                    raise error.pop(0)
            else:
                raise error
        return RawDocument(ref=ref, payload={"body": "x"}, media_type="application/json")


def _ref(n: int, url: str | None = None) -> SourceRef:
    return SourceRef(
        source_id="stub",
        external_id=f"doc-{n}",
        url=url or f"https://example.test/doc-{n}",
        content_hash=f"hash-{n}",
    )


@pytest.fixture
def tracker() -> JobTracker:
    return JobTracker(FakeJobRepo())


def _build(adapter, tracker, settings, policy=None, sleeps=None):
    return IngestionOrchestrator(
        adapter,
        tracker,
        policy or StubPolicy(),
        ChangeDetector(),
        settings=settings,
        sleep=(sleeps.append if sleeps is not None else (lambda _s: None)),
    )


class TestHappyPath:
    def test_all_documents_processed(self, tracker, settings):
        adapter = StubAdapter([_ref(1), _ref(2), _ref(3)])
        job_id = tracker.create(JobKind.INGEST, {})
        outcome = _build(adapter, tracker, settings).run(
            job_id, None, lambda ref: None, lambda raw: 100
        )
        assert (outcome.succeeded, outcome.skipped, outcome.failed) == (3, 0, 0)


class TestPartialFailure:
    def test_one_bad_document_does_not_stop_the_run(self, tracker, settings):
        """BR-40 — the whole reason job items exist."""
        adapter = StubAdapter(
            [_ref(1), _ref(2), _ref(3)],
            failures={"stub:doc-2": ExtractionError("scanned pdf")},
        )
        job_id = tracker.create(JobKind.INGEST, {})
        outcome = _build(adapter, tracker, settings).run(
            job_id, None, lambda ref: None, lambda raw: 100
        )
        assert outcome.succeeded == 2
        assert outcome.failed == 1
        assert outcome.failures_by_kind == {FailureKind.PERMANENT.value: 1}
        assert adapter.fetch_calls == ["stub:doc-1", "stub:doc-2", "stub:doc-3"]

    def test_failure_reason_is_recorded_per_item(self, tracker, settings):
        adapter = StubAdapter([_ref(1)], failures={"stub:doc-1": ExtractionError("scanned")})
        job_id = tracker.create(JobKind.INGEST, {})
        _build(adapter, tracker, settings).run(job_id, None, lambda ref: None, lambda raw: 1)
        item = tracker._repo.get_item(job_id, "stub:doc-1")
        assert item.failure_kind == FailureKind.PERMANENT.value
        assert "scanned" in item.failure_reason


class TestRetry:
    def test_transient_failure_is_retried_then_succeeds(self, tracker, settings):
        """BR-41 — two transient failures, then the third attempt lands."""
        sleeps: list[float] = []
        adapter = StubAdapter(
            [_ref(1)],
            failures={
                "stub:doc-1": [
                    SourceUnavailableError("503"),
                    SourceUnavailableError("503"),
                ]
            },
        )
        job_id = tracker.create(JobKind.INGEST, {})
        outcome = _build(adapter, tracker, settings, sleeps=sleeps).run(
            job_id, None, lambda ref: None, lambda raw: 42
        )
        assert outcome.succeeded == 1
        assert len(adapter.fetch_calls) == 3
        assert sleeps == [1.0, 4.0]

    def test_permanent_failure_is_not_retried(self, tracker, settings):
        """BR-42 — repeating the same bytes gives the same answer."""
        sleeps: list[float] = []
        adapter = StubAdapter([_ref(1)], failures={"stub:doc-1": ExtractionError("bad")})
        job_id = tracker.create(JobKind.INGEST, {})
        _build(adapter, tracker, settings, sleeps=sleeps).run(
            job_id, None, lambda ref: None, lambda raw: 1
        )
        assert len(adapter.fetch_calls) == 1
        assert sleeps == []

    def test_retries_stop_at_the_limit(self, tracker, settings):
        adapter = StubAdapter([_ref(1)], failures={"stub:doc-1": SourceUnavailableError("503")})
        job_id = tracker.create(JobKind.INGEST, {})
        outcome = _build(adapter, tracker, settings).run(
            job_id, None, lambda ref: None, lambda raw: 1
        )
        assert outcome.failed == 1
        assert len(adapter.fetch_calls) == settings.max_retry_attempts


class TestPolicy:
    def test_blocked_url_is_never_fetched(self, tracker, settings):
        """BR-03 / BR-04 — the policy check happens before the request, and there
        is no fallback path that could sneak one through."""
        blocked = "https://example.test/doc-2"
        adapter = StubAdapter([_ref(1), _ref(2, blocked), _ref(3)])
        job_id = tracker.create(JobKind.INGEST, {})
        outcome = _build(
            adapter, tracker, settings, policy=StubPolicy(frozenset({blocked}))
        ).run(job_id, None, lambda ref: None, lambda raw: 1)

        assert "stub:doc-2" not in adapter.fetch_calls
        assert outcome.succeeded == 2
        assert outcome.failures_by_kind == {FailureKind.POLICY_BLOCKED.value: 1}

    def test_blocked_item_is_skipped_on_rerun(self, tracker, settings):
        """BR-43 — unlike a permanent failure, this is not re-attempted."""
        blocked = "https://example.test/doc-1"
        adapter = StubAdapter([_ref(1, blocked)])
        job_id = tracker.create(JobKind.INGEST, {})
        orchestrator = _build(adapter, tracker, settings, policy=StubPolicy(frozenset({blocked})))
        orchestrator.run(job_id, None, lambda ref: None, lambda raw: 1)

        # second pass over the same job
        second = orchestrator.run(job_id, None, lambda ref: None, lambda raw: 1)
        assert adapter.fetch_calls == []
        assert second.succeeded == 0


class TestIncremental:
    def test_unchanged_document_is_skipped_without_fetching(self, tracker, settings):
        """BR-09 / BR-11 — and a skip is not a failure."""

        @dataclass
        class Known:
            id: int = 1
            content_hash: str = "hash-1"
            published_at: None = None
            revised_at: None = None

        adapter = StubAdapter([_ref(1), _ref(2)])
        job_id = tracker.create(JobKind.INGEST, {})

        def known_for(ref: SourceRef):
            return Known() if ref.external_id == "doc-1" else None

        outcome = _build(adapter, tracker, settings).run(
            job_id, None, known_for, lambda raw: 7
        )
        assert outcome.skipped == 1
        assert outcome.succeeded == 1
        assert outcome.failed == 0
        assert "stub:doc-1" not in adapter.fetch_calls
