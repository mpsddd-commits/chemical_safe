"""Job state — BR-46 ~ BR-51.

Uses an in-memory stand-in for JobRepo. That substitution is only possible
because domain components take repositories rather than sessions (DD-20).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.core.errors import FailureKind
from app.core.types import ItemStatus, JobKind, JobStatus, PipelineStage
from app.jobs.tracker import JobTracker


@dataclass
class FakeItem:
    ref_key: str
    status: str = ItemStatus.PENDING.value
    last_stage: str | None = None
    failure_kind: str | None = None
    failure_reason: str | None = None
    attempt_count: int = 0
    document_id: int | None = None


@dataclass
class FakeJob:
    id: int
    kind: str
    params: dict
    status: str = JobStatus.PENDING.value
    total_count: int = 0
    success_count: int = 0
    skipped_count: int = 0
    failure_count: int = 0
    started_at: object | None = None
    finished_at: object | None = None
    items: list[FakeItem] = field(default_factory=list)


class FakeJobRepo:
    """Mirrors the real repository's contract, including the counter bookkeeping."""

    def __init__(self) -> None:
        self.jobs: dict[int, FakeJob] = {}
        self._next_id = 1

    def create(self, kind: JobKind, params: dict) -> FakeJob:
        job = FakeJob(id=self._next_id, kind=kind.value, params=params)
        self.jobs[job.id] = job
        self._next_id += 1
        return job

    def get(self, job_id: int) -> FakeJob | None:
        return self.jobs.get(job_id)

    def mark_running(self, job: FakeJob) -> None:
        job.status = JobStatus.RUNNING.value
        job.started_at = "now"

    def add_items(self, job: FakeJob, ref_keys: list[str]) -> int:
        existing = {i.ref_key for i in job.items}
        added = 0
        for key in ref_keys:
            if key in existing:
                continue
            job.items.append(FakeItem(ref_key=key))
            existing.add(key)
            added += 1
        job.total_count = len(job.items)
        return added

    def get_item(self, job_id: int, ref_key: str) -> FakeItem | None:
        job = self.jobs[job_id]
        return next((i for i in job.items if i.ref_key == ref_key), None)

    def mark_item(self, job, ref_key, status, *, document_id=None, last_stage=None,
                  failure_kind=None, failure_reason=None, attempt_count=None):
        item = self.get_item(job.id, ref_key)
        if item is None:
            item = FakeItem(ref_key=ref_key)
            job.items.append(item)
        previous = item.status
        item.status = status.value
        if document_id is not None:
            item.document_id = document_id
        if last_stage is not None:
            item.last_stage = last_stage.value
        item.failure_kind = failure_kind
        item.failure_reason = failure_reason
        if attempt_count is not None:
            item.attempt_count = attempt_count
        counters = {
            ItemStatus.SUCCEEDED.value: "success_count",
            ItemStatus.SKIPPED.value: "skipped_count",
            ItemStatus.FAILED.value: "failure_count",
        }
        if previous in counters:
            setattr(job, counters[previous], max(0, getattr(job, counters[previous]) - 1))
        if status.value in counters:
            setattr(job, counters[status.value], getattr(job, counters[status.value]) + 1)
        return item

    def finalize(self, job: FakeJob) -> JobStatus:
        if job.failure_count == 0:
            status = JobStatus.SUCCEEDED
        elif job.success_count > 0 or job.skipped_count > 0:
            status = JobStatus.PARTIAL
        else:
            status = JobStatus.FAILED
        job.status = status.value
        job.finished_at = "now"
        return status

    def resume_items(self, job_id: int) -> list[FakeItem]:
        job = self.jobs[job_id]
        return [
            i
            for i in job.items
            if i.status in {ItemStatus.PENDING.value, ItemStatus.RUNNING.value,
                            ItemStatus.FAILED.value}
            and i.failure_kind != FailureKind.POLICY_BLOCKED.value
        ]

    def blocked_ref_keys(self, job_id: int) -> set[str]:
        return {
            i.ref_key
            for i in self.jobs[job_id].items
            if i.failure_kind == FailureKind.POLICY_BLOCKED.value
        }


@pytest.fixture
def tracker() -> JobTracker:
    return JobTracker(FakeJobRepo())


class TestFinalStatus:
    def test_all_success(self, tracker):
        job_id = tracker.create(JobKind.INGEST, {})
        tracker.add_items(job_id, ["a", "b"])
        tracker.mark_succeeded(job_id, "a", 1)
        tracker.mark_succeeded(job_id, "b", 2)
        assert tracker.finalize(job_id) is JobStatus.SUCCEEDED

    def test_some_success_some_failure_is_partial(self, tracker):
        job_id = tracker.create(JobKind.INGEST, {})
        tracker.add_items(job_id, ["a", "b"])
        tracker.mark_succeeded(job_id, "a", 1)
        tracker.mark_failed(job_id, "b", FailureKind.PERMANENT, "bad pdf")
        assert tracker.finalize(job_id) is JobStatus.PARTIAL

    def test_all_failed(self, tracker):
        job_id = tracker.create(JobKind.INGEST, {})
        tracker.add_items(job_id, ["a"])
        tracker.mark_failed(job_id, "a", FailureKind.PERMANENT, "bad pdf")
        assert tracker.finalize(job_id) is JobStatus.FAILED

    def test_all_skipped_is_success(self, tracker):
        """BR-49 — 'nothing changed' is the normal outcome of a re-run."""
        job_id = tracker.create(JobKind.INGEST, {})
        tracker.add_items(job_id, ["a", "b"])
        tracker.mark_skipped(job_id, "a")
        tracker.mark_skipped(job_id, "b")
        assert tracker.finalize(job_id) is JobStatus.SUCCEEDED

    def test_skipped_plus_failure_is_partial(self, tracker):
        job_id = tracker.create(JobKind.INGEST, {})
        tracker.add_items(job_id, ["a", "b"])
        tracker.mark_skipped(job_id, "a")
        tracker.mark_failed(job_id, "b", FailureKind.TRANSIENT, "timeout")
        assert tracker.finalize(job_id) is JobStatus.PARTIAL

    def test_empty_job_is_success(self, tracker):
        job_id = tracker.create(JobKind.INGEST, {})
        assert tracker.finalize(job_id) is JobStatus.SUCCEEDED


class TestProgress:
    def test_zero_targets_reports_zero(self, tracker):
        """BR-50 — no division by zero, and no misleading 100%."""
        job_id = tracker.create(JobKind.INGEST, {})
        assert tracker.progress(job_id).ratio == 0.0

    def test_ratio_counts_skipped_as_done(self, tracker):
        job_id = tracker.create(JobKind.INGEST, {})
        tracker.add_items(job_id, ["a", "b", "c", "d"])
        tracker.mark_succeeded(job_id, "a", 1)
        tracker.mark_skipped(job_id, "b")
        assert tracker.progress(job_id).ratio == 0.5

    def test_status_change_does_not_double_count(self, tracker):
        job_id = tracker.create(JobKind.INGEST, {})
        tracker.add_items(job_id, ["a"])
        tracker.mark_failed(job_id, "a", FailureKind.TRANSIENT, "timeout")
        tracker.mark_succeeded(job_id, "a", 7)
        progress = tracker.progress(job_id)
        assert (progress.success_count, progress.failure_count) == (1, 0)


class TestResume:
    def test_failed_items_are_offered_for_resume(self, tracker):
        """BR-45 — a permanent failure is retried next run; the source may have
        been fixed."""
        job_id = tracker.create(JobKind.INGEST, {})
        tracker.add_items(job_id, ["a", "b"])
        tracker.mark_succeeded(job_id, "a", 1)
        tracker.mark_failed(
            job_id, "b", FailureKind.PERMANENT, "bad pdf", last_stage=PipelineStage.EXTRACT
        )
        resume = dict(tracker.resume_point(job_id))
        assert "a" not in resume
        assert resume["b"] is PipelineStage.EXTRACT

    def test_policy_blocked_is_never_offered_for_resume(self, tracker):
        """BR-43 — the distinction from PERMANENT exists for exactly this."""
        job_id = tracker.create(JobKind.INGEST, {})
        tracker.add_items(job_id, ["blocked"])
        tracker.mark_failed(job_id, "blocked", FailureKind.POLICY_BLOCKED, "robots disallow")
        assert tracker.resume_point(job_id) == []
        assert tracker.blocked_ref_keys(job_id) == {"blocked"}


class TestSecretMasking:
    def test_failure_reason_is_masked(self, tracker):
        """BR-60 — a failing URL often carries the key that failed."""
        job_id = tracker.create(JobKind.INGEST, {})
        tracker.add_items(job_id, ["a"])
        tracker.mark_failed(
            job_id,
            "a",
            FailureKind.TRANSIENT,
            "HTTP 500 from https://api.test/list?serviceKey=SUPERSECRET123&page=1",
        )
        item = tracker._repo.get_item(job_id, "a")
        assert "SUPERSECRET123" not in item.failure_reason
        assert "***" in item.failure_reason
