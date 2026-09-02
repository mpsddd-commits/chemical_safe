"""JSON API routes.

Routers validate, serialise and delegate; every orchestration decision lives in
the service layer (DD-12). The HTML routes in `admin.py` call the same service
methods, so the two views cannot drift apart.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.types import ItemStatus, JobKind, JobStatus
from app.db.engine import session_scope
from app.services.indexing_service import IndexingService
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/api", tags=["api"])


def get_session() -> Session:
    with session_scope() as session:
        yield session


class IngestRequest(BaseModel):
    since: date | None = None

    @field_validator("since")
    @classmethod
    def _not_future(cls, value: date | None) -> date | None:
        # Server-side validation is authoritative; the form check is a courtesy
        # (NFR-17).
        if value and value > datetime.now(UTC).date():
            raise ValueError("since cannot be in the future")
        return value


class IngestResponse(BaseModel):
    job_id: int | None
    accepted: bool
    reason: str | None = None


@router.get("/sources")
def list_sources(session: Session = Depends(get_session)) -> list[dict]:
    return IngestionService(session).list_sources()


@router.post("/sources/{source_id}/ingest", response_model=IngestResponse)
def start_ingest(
    source_id: str,
    payload: IngestRequest | None = None,
    session: Session = Depends(get_session),
) -> IngestResponse:
    since = None
    if payload and payload.since:
        since = datetime.combine(payload.since, datetime.min.time(), tzinfo=UTC)
    result = IngestionService(session).start_and_enqueue(source_id, since)
    if not result.accepted:
        # 409: the request was understood but the source cannot be collected
        # right now (missing key, or blocked by policy).
        raise HTTPException(status_code=409, detail=result.reason)
    return IngestResponse(job_id=result.job_id, accepted=True)


@router.get("/jobs")
def list_jobs(
    status: list[str] | None = Query(default=None),
    kind: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[dict]:
    # Unknown enum values are ignored rather than rejected, so a stale bookmark
    # still renders the default list.
    valid_status = [s for s in (status or []) if s in {e.value for e in JobStatus}]
    valid_kind = kind if kind in {e.value for e in JobKind} else None
    jobs = IngestionService(session).list_jobs(
        statuses=valid_status or None, kind=valid_kind, limit=limit
    )
    return [_job_dict(j) for j in jobs]


@router.get("/jobs/{job_id}")
def job_detail(job_id: int, session: Session = Depends(get_session)) -> dict:
    service = IngestionService(session)
    try:
        progress = service.job_status(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "job_id": progress.job_id,
        "status": progress.status.value,
        "total_count": progress.total_count,
        "success_count": progress.success_count,
        "skipped_count": progress.skipped_count,
        "failure_count": progress.failure_count,
        "ratio": progress.ratio,
    }


@router.get("/jobs/{job_id}/items")
def job_items(
    job_id: int,
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
) -> list[dict]:
    valid_status = status if status in {e.value for e in ItemStatus} else None
    items = IngestionService(session).job_items(job_id, status=valid_status, limit=limit)
    return [
        {
            "ref_key": i.ref_key,
            "status": i.status,
            "last_stage": i.last_stage,
            "failure_kind": i.failure_kind,
            "failure_reason": i.failure_reason,
            "attempt_count": i.attempt_count,
            "document_id": i.document_id,
        }
        for i in items
    ]


@router.get("/stats")
def stats(session: Session = Depends(get_session)) -> dict:
    return IndexingService(session).stats()


def _job_dict(job) -> dict:
    total = job.total_count or 0
    done = job.success_count + job.skipped_count + job.failure_count
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "params": job.params,
        "total_count": total,
        "success_count": job.success_count,
        "skipped_count": job.skipped_count,
        "failure_count": job.failure_count,
        # BR-50 - a job with no targets shows 0%, not a division error.
        "ratio": (done / total) if total else 0.0,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
