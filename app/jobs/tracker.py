"""C28 JobTracker - progress, partial failure and resume points (BR-46~51).

Job state lives in our own tables, not in the queue backend (DD-13). That is what
lets `docker compose down` take Redis with it without losing the ability to say
what already succeeded.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from app.core.errors import FailureKind
from app.core.logging import get_logger, mask_secrets
from app.core.types import ItemStatus, JobKind, JobProgress, JobStatus, PipelineStage
from app.db.repositories.jobs import JobRepo

log = get_logger(__name__)

MAX_REASON_CHARS = 2000


class JobTracker:
    """Progress is committed as it happens, not at the end of the run.

    Without `commit`, a whole job lives in one transaction: `/admin/jobs/{id}`
    shows `pending / 0 of 0` for hours while work is clearly happening, and a
    crash discards every completed item. Build & Test caught exactly that. The
    caller supplies its own commit so the tracker still owns no session.
    """

    def __init__(self, job_repo: JobRepo, commit: Callable[[], None] | None = None) -> None:
        self._repo = job_repo
        self._commit = commit

    def _flush(self) -> None:
        if self._commit is not None:
            self._commit()

    def create(self, kind: JobKind, params: dict) -> int:
        job = self._repo.create(kind, params)
        log.info("job_created", extra={"job_id": job.id, "kind": kind.value})
        self._flush()
        return job.id

    def start(self, job_id: int) -> None:
        job = self._require(job_id)
        self._repo.mark_running(job)
        self._flush()
        log.info("job_started", extra={"job_id": job_id})

    def add_items(self, job_id: int, ref_keys: list[str]) -> int:
        job = self._require(job_id)
        added = self._repo.add_items(job, ref_keys)
        log.info("job_items_added", extra={"job_id": job_id, "added": added})
        self._flush()
        return added

    def mark_succeeded(
        self, job_id: int, ref_key: str, document_id: int, attempts: int = 1
    ) -> None:
        job = self._require(job_id)
        self._repo.mark_item(
            job,
            ref_key,
            ItemStatus.SUCCEEDED,
            document_id=document_id,
            last_stage=PipelineStage.PERSIST,
            attempt_count=attempts,
        )
        self._flush()

    def mark_skipped(self, job_id: int, ref_key: str) -> None:
        """BR-11 - unchanged is not a failure."""
        job = self._require(job_id)
        self._repo.mark_item(job, ref_key, ItemStatus.SKIPPED)
        self._flush()

    def mark_failed(
        self,
        job_id: int,
        ref_key: str,
        kind: FailureKind,
        reason: str,
        *,
        last_stage: PipelineStage | None = None,
        attempts: int = 1,
    ) -> None:
        job = self._require(job_id)
        self._repo.mark_item(
            job,
            ref_key,
            ItemStatus.FAILED,
            last_stage=last_stage,
            failure_kind=kind.value,
            # BR-60 - the reason may quote a URL that carried a key.
            failure_reason=mask_secrets(reason)[:MAX_REASON_CHARS],
            attempt_count=attempts,
        )
        log.warning(
            "job_item_failed",
            extra={
                "job_id": job_id,
                "ref_key": ref_key,
                "failure_kind": kind.value,
                "last_stage": last_stage.value if last_stage else None,
            },
        )
        self._flush()

    def progress(self, job_id: int) -> JobProgress:
        job = self._require(job_id)
        return JobProgress(
            job_id=job.id,
            status=JobStatus(job.status),
            total_count=job.total_count,
            success_count=job.success_count,
            skipped_count=job.skipped_count,
            failure_count=job.failure_count,
        )

    def finalize(self, job_id: int) -> JobStatus:
        job = self._require(job_id)
        status = self._repo.finalize(job)
        log.info(
            "job_finished",
            extra={
                "job_id": job_id,
                "status": status.value,
                "success": job.success_count,
                "skipped": job.skipped_count,
                "failed": job.failure_count,
            },
        )
        self._flush()
        return status

    def resume_point(self, job_id: int) -> list[tuple[str, PipelineStage | None]]:
        """BR-44 / BR-45 - unfinished work, with the stage each item reached.

        `policy_blocked` items are absent by construction: they must not be
        re-attempted until the policy itself changes (BR-43).
        """
        items = self._repo.resume_items(job_id)
        return [
            (i.ref_key, PipelineStage(i.last_stage) if i.last_stage else None) for i in items
        ]

    def blocked_ref_keys(self, job_id: int) -> set[str]:
        return self._repo.blocked_ref_keys(job_id)

    def _require(self, job_id: int):
        job = self._repo.get(job_id)
        if job is None:
            raise LookupError(f"job {job_id} not found")
        return job


def utcnow() -> datetime:
    return datetime.now(UTC)
