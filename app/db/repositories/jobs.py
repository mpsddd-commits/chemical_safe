"""JobRepo and TraceRepo.

Job state is owned by these tables, not by the queue backend (DD-13). That is
what makes the queue a replaceable detail and what lets a restarted worker pick
up exactly where it stopped.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import ItemStatus, JobKind, JobStatus, PipelineStage
from app.db.models import Job, JobItem, WorkerHeartbeat


class JobRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    # ---- Job ----
    def create(self, kind: JobKind, params: dict) -> Job:
        job = Job(kind=kind.value, params=params, status=JobStatus.PENDING.value)
        self._s.add(job)
        self._s.flush()
        return job

    def get(self, job_id: int) -> Job | None:
        return self._s.get(Job, job_id)

    def list_jobs(
        self,
        statuses: list[str] | None = None,
        kind: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[Job]:
        stmt = select(Job).order_by(Job.created_at.desc())
        if statuses:
            stmt = stmt.where(Job.status.in_(statuses))
        if kind:
            stmt = stmt.where(Job.kind == kind)
        return list(self._s.scalars(stmt.limit(limit).offset(offset)))

    def mark_running(self, job: Job) -> None:
        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        self._s.flush()

    def finalize(self, job: Job) -> JobStatus:
        """BR-48 / BR-49.

        A run where every item was skipped (nothing changed) is a success, not a
        failure - that is the normal outcome of an incremental re-run.
        """
        if job.failure_count == 0:
            status = JobStatus.SUCCEEDED
        elif job.success_count > 0 or job.skipped_count > 0:
            status = JobStatus.PARTIAL
        else:
            status = JobStatus.FAILED
        job.status = status.value
        job.finished_at = datetime.now(UTC)
        self._s.flush()
        return status

    # ---- JobItem ----
    def add_items(self, job: Job, ref_keys: list[str]) -> int:
        existing = {i.ref_key for i in job.items}
        added = 0
        for key in ref_keys:
            if key in existing:
                continue
            self._s.add(JobItem(job_id=job.id, ref_key=key, status=ItemStatus.PENDING.value))
            existing.add(key)
            added += 1
        job.total_count = len(existing)
        self._s.flush()
        return added

    def get_item(self, job_id: int, ref_key: str) -> JobItem | None:
        return self._s.scalar(
            select(JobItem).where(JobItem.job_id == job_id, JobItem.ref_key == ref_key)
        )

    def list_items(
        self, job_id: int, status: str | None = None, limit: int = 200
    ) -> list[JobItem]:
        stmt = select(JobItem).where(JobItem.job_id == job_id).order_by(JobItem.id)
        if status:
            stmt = stmt.where(JobItem.status == status)
        return list(self._s.scalars(stmt.limit(limit)))

    def mark_item(
        self,
        job: Job,
        ref_key: str,
        status: ItemStatus,
        *,
        document_id: int | None = None,
        last_stage: PipelineStage | None = None,
        failure_kind: str | None = None,
        failure_reason: str | None = None,
        attempt_count: int | None = None,
    ) -> JobItem:
        item = self.get_item(job.id, ref_key)
        if item is None:
            item = JobItem(job_id=job.id, ref_key=ref_key)
            self._s.add(item)
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
        self._s.flush()
        self._recount(job, previous, status)
        return item

    def _recount(self, job: Job, previous: str, current: ItemStatus) -> None:
        counters = {
            ItemStatus.SUCCEEDED.value: "success_count",
            ItemStatus.SKIPPED.value: "skipped_count",
            ItemStatus.FAILED.value: "failure_count",
        }
        if previous in counters:
            attr = counters[previous]
            setattr(job, attr, max(0, getattr(job, attr) - 1))
        if current.value in counters:
            attr = counters[current.value]
            setattr(job, attr, getattr(job, attr) + 1)
        self._s.flush()

    def resume_items(self, job_id: int) -> list[JobItem]:
        """BR-44 / BR-45 - everything that is not yet done.

        ``policy_blocked`` failures are excluded: they must not be retried until
        the policy check itself flips to allowed (BR-43).
        """
        return list(
            self._s.scalars(
                select(JobItem).where(
                    JobItem.job_id == job_id,
                    JobItem.status.in_(
                        [
                            ItemStatus.PENDING.value,
                            ItemStatus.RUNNING.value,
                            ItemStatus.FAILED.value,
                        ]
                    ),
                    (JobItem.failure_kind.is_(None)) | (JobItem.failure_kind != "policy_blocked"),
                )
            )
        )

    def blocked_ref_keys(self, job_id: int) -> set[str]:
        rows = self._s.scalars(
            select(JobItem.ref_key).where(
                JobItem.job_id == job_id, JobItem.failure_kind == "policy_blocked"
            )
        )
        return set(rows)


class WorkerHeartbeatRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def beat(self, worker_id: str) -> None:
        row = self._s.get(WorkerHeartbeat, worker_id)
        if row is None:
            self._s.add(WorkerHeartbeat(worker_id=worker_id, beat_at=datetime.now(UTC)))
        else:
            row.beat_at = datetime.now(UTC)
        self._s.flush()

    def any_alive(self, stale_threshold_seconds: int) -> bool:
        """BR-52 - the worker health probe."""
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_threshold_seconds)
        latest = self._s.scalar(select(func.max(WorkerHeartbeat.beat_at)))
        return latest is not None and latest >= cutoff


class TraceRepo:
    """Written by the tracing decorator (C13), read by u2 usage reporting.

    In u1 nothing calls an LLM, so this only ever records embedding calls.
    """

    def __init__(self, session: Session) -> None:
        self._s = session
        self._buffer: list[dict] = []

    def record(self, **fields: object) -> None:
        # The trace table itself arrives with the u2 migration (0002_query).
        # Until then calls are buffered in-process and emitted to the log, which
        # keeps the decorator's contract stable across units (DD-16, DD-21).
        self._buffer.append(dict(fields))

    def drain(self) -> list[dict]:
        items, self._buffer = self._buffer, []
        return items
