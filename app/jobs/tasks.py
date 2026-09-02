"""Worker task handlers.

Handlers are thin: they open a session, build the services and delegate. All
orchestration lives in the service layer (DD-12) so the same code path runs from
the CLI without a queue.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import bind, get_logger
from app.db.engine import session_scope

log = get_logger(__name__)


def _ingest_sync(job_id: int, source_id: str, since: str | None) -> dict[str, Any]:
    from app.services.ingestion_service import IngestionService

    bind(f"job-{job_id}")
    with session_scope() as session:
        return IngestionService(session).execute(
            job_id=job_id, source_id=source_id, since=since
        )


async def run_ingest(ctx: dict[str, Any], job_id: int, source_id: str,
                     since: str | None = None) -> dict[str, Any]:
    """Executes one ingestion job (W1 step 6 onwards).

    The body is synchronous - database work and embedding inference both block -
    so it runs in a worker thread. Calling it directly held arq's event loop for
    the whole job: measured on a 9-statute run, the BR-52 heartbeat did not tick
    once in 37 minutes, so `/healthz` reported the worker *down* while it was
    working correctly, and arq eventually lost its Redis connection outright
    (`redis.exceptions.TimeoutError`) and the process died. `job_timeout` is set
    to 8 hours for the initial index (NFR-4); without this the connection does
    not survive anywhere near that long.
    """
    outcome = await asyncio.to_thread(_ingest_sync, job_id, source_id, since)
    log.info("task_ingest_done", extra={"job_id": job_id, **outcome})
    return outcome


def _reindex_sync(job_id: int, scope: str) -> dict[str, Any]:
    from app.services.indexing_service import IndexingService

    bind(f"job-{job_id}")
    with session_scope() as session:
        return IndexingService(session).reindex_job(job_id=job_id, scope=scope)


async def run_reindex(ctx: dict[str, Any], job_id: int, scope: str = "all") -> dict[str, Any]:
    """Re-index without re-collecting when originals are retained (FQ-8=A).

    Threaded for the same reason as `run_ingest`: re-indexing the whole corpus
    re-embeds every chunk, which is the longest-running job in the system.
    """
    outcome = await asyncio.to_thread(_reindex_sync, job_id, scope)
    log.info("task_reindex_done", extra={"job_id": job_id, **outcome})
    return outcome


def _index_upload_sync(document_id: int, job_id: int | None = None) -> dict[str, Any]:
    """BR-142 - the same indexing path the public corpus goes through.

    `reindex_document` reads the retained file and re-runs extraction, chunking
    and embedding with the document's own `owner_id`, so an uploaded PDF is cut
    into chunks by exactly the rules a collected one is. A separate upload-only
    path would let those rules drift, and then the same document would be cited
    two different ways depending on where it came from.
    """
    from app.core.errors import FailureKind, SafeenvError
    from app.db.repositories.jobs import JobRepo
    from app.jobs.tracker import JobTracker
    from app.services.indexing_service import IndexingService

    bind(f"upload-{document_id}")
    ref_key = f"upload:{document_id}"
    try:
        with session_scope() as session:
            if job_id is not None:
                JobTracker(JobRepo(session), commit=session.commit).start(job_id)
            outcome = IndexingService(session).reindex_document(document_id)
            if job_id is not None:
                tracker = JobTracker(JobRepo(session), commit=session.commit)
                tracker.mark_succeeded(job_id, ref_key, document_id)
                tracker.finalize(job_id)
            return {
                "document_id": document_id,
                "chunks": outcome.chunk_count,
                "structure_status": outcome.structure_status,
            }
    except Exception as exc:
        # The failure has to reach the person who uploaded the file. Measured on
        # a blank PDF: `ExtractionError: PDF produced no usable text` was logged
        # and the document sat at zero chunks, so the screen said "indexing" and
        # kept saying it. Scanned MSDS PDFs hit exactly this path.
        kind = exc.kind if isinstance(exc, SafeenvError) else FailureKind.PERMANENT
        if job_id is not None:
            with session_scope() as session:
                tracker = JobTracker(JobRepo(session), commit=session.commit)
                tracker.mark_failed(job_id, ref_key, kind, str(exc))
                tracker.finalize(job_id)
        raise


async def run_index_upload(
    ctx: dict[str, Any], document_id: int, job_id: int | None = None
) -> dict[str, Any]:
    """FR-27 - a user upload becomes searchable, asynchronously (BR-143)."""
    outcome = await asyncio.to_thread(_index_upload_sync, document_id, job_id)
    log.info("task_index_upload_done", extra=outcome)
    return outcome


TASKS = [run_ingest, run_reindex, run_index_upload]
