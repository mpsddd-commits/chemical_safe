"""HTML routes for the operations screens (FR-48).

Server-rendered, form-driven, no JSON round-trips. Every screen works with
JavaScript disabled; `app.js` only adds auto-refresh and snippet toggles
(DD-17).

**B1 - the whole router is admin-only.** Measured before the change: all four
GETs answered anonymous callers with 200, and the POST that starts a collection
job was reachable the same way. The guard is declared on `APIRouter(...)`
rather than on each of the five handlers for the reason B2a gives: the way this
gap reappears is somebody adding a sixth route, and a router-level default is
the only version of the rule that they cannot skip by not knowing about it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.types import AuthenticatedUser
from app.core.types import ItemStatus, JobKind, JobStatus
from app.web.deps import require_admin
from app.web.routers.api import _job_dict, get_session

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])

# B1 - reaching any handler in this file means `require_admin` already passed,
# so the navigation flag is a constant here, not something to look up again.
# It used to come from `admin_flag`, which opens its own session per render;
# keeping that call would spend a second SELECT to re-derive an answer this
# request has already proved, and would leave two places that could disagree
# about whether this viewer is an admin.
IS_ADMIN = True

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

MAX_LIMIT = 100
DEFAULT_LIMIT = 25


def _clean_limit(raw: int | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    if raw < 1 or raw > MAX_LIMIT:
        return DEFAULT_LIMIT
    return raw


# Moved from "/" in u2. The root belongs to the query screen (P5, FR-14) - it is
# what this system is for, and the operations dashboard is a tool for running it.
@router.get("/admin", response_class=HTMLResponse)
def dashboard(
    request: Request,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(require_admin),
) -> HTMLResponse:
    from app.services.indexing_service import IndexingService
    from app.services.ingestion_service import IngestionService

    stats = IndexingService(session).stats()
    recent = [_job_dict(j) for j in IngestionService(session).list_jobs(limit=5)]
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        # B1 - `user` travels with `is_admin`, because `base.html` reads both
        # and B3 passed only the second. Measured on the running container: an
        # admin on this page saw the admin navigation, the "로그인하지 않음"
        # banner, and a "로그인" link, all at once - the page disagreed with
        # itself about who was looking at it. `require_admin` in the signature
        # rather than relying on the router-level guard alone: the handler
        # needs the value, and FastAPI resolves the same dependency once per
        # request, so this costs no extra query.
        context={
            "stats": stats,
            "recent_jobs": recent,
            "active": "dashboard",
            "user": user,
            "is_admin": IS_ADMIN,
        },
    )


@router.get("/admin/sources", response_class=HTMLResponse)
def sources_page(
    request: Request,
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(require_admin),
) -> HTMLResponse:
    from app.services.ingestion_service import IngestionService

    service = IngestionService(session)
    service.sync_source_catalog()
    return templates.TemplateResponse(
        request=request,
        name="sources.html",
        context={
            "sources": service.list_sources(),
            "today": datetime.now(UTC).date().isoformat(),
            "active": "sources",
            "user": user,
            "is_admin": IS_ADMIN,
        },
    )


@router.post("/admin/sources/{source_id}/ingest")
def start_ingest_form(
    source_id: str,
    since: str = Form(default=""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    from app.services.ingestion_service import IngestionService

    since_dt = None
    if since:
        try:
            parsed = date.fromisoformat(since)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="since must be YYYY-MM-DD") from exc
        if parsed > datetime.now(UTC).date():
            raise HTTPException(status_code=400, detail="since cannot be in the future")
        since_dt = datetime.combine(parsed, datetime.min.time(), tzinfo=UTC)

    result = IngestionService(session).start_and_enqueue(source_id, since_dt)
    if not result.accepted:
        raise HTTPException(status_code=409, detail=result.reason)
    # 303 so a browser refresh does not resubmit the form.
    return RedirectResponse(url=f"/admin/jobs/{result.job_id}", status_code=303)


@router.get("/admin/jobs", response_class=HTMLResponse)
def jobs_page(
    request: Request,
    status: list[str] | None = Query(default=None),
    kind: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(require_admin),
) -> HTMLResponse:
    from app.services.ingestion_service import IngestionService

    valid_status = [s for s in (status or []) if s in {e.value for e in JobStatus}]
    valid_kind = kind if kind in {e.value for e in JobKind} else None
    jobs = IngestionService(session).list_jobs(
        statuses=valid_status or None, kind=valid_kind, limit=_clean_limit(limit)
    )
    return templates.TemplateResponse(
        request=request,
        name="jobs.html",
        context={
            "jobs": [_job_dict(j) for j in jobs],
            "statuses": [e.value for e in JobStatus],
            "kinds": [e.value for e in JobKind],
            "selected_status": valid_status,
            "selected_kind": valid_kind,
            "active": "jobs",
            "user": user,
            "is_admin": IS_ADMIN,
        },
    )


@router.get("/admin/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(
    request: Request,
    job_id: int,
    status: str | None = Query(default=None),
    session: Session = Depends(get_session),
    user: AuthenticatedUser = Depends(require_admin),
) -> HTMLResponse:
    from app.services.ingestion_service import IngestionService

    service = IngestionService(session)
    try:
        progress = service.job_status(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    valid_status = status if status in {e.value for e in ItemStatus} else None
    items = service.job_items(job_id, status=valid_status)
    job = service.list_jobs(limit=1000)
    job_row = next((j for j in job if j.id == job_id), None)

    return templates.TemplateResponse(
        request=request,
        name="job_detail.html",
        context={
            "job": _job_dict(job_row) if job_row else None,
            "progress": progress,
            "items": items,
            "item_statuses": [e.value for e in ItemStatus],
            "selected_status": valid_status,
            # Auto-refresh is offered only while there is something to watch.
            "is_running": progress.status
            in (JobStatus.PENDING, JobStatus.RUNNING),
            "active": "jobs",
            "user": user,
            "is_admin": IS_ADMIN,
        },
    )
