"""Usage routes - P6 (FR-42, NFR-19).

The JSON and the HTML view call the same service method, so the two cannot
drift into disagreeing about what a period cost (DD-12).

⚠️ Like u1's `/admin`, this screen has no authentication until u5. Loopback
binding (NFR-18) is the only access control, and it was verified by measurement
in u1 Build & Test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.types import LlmPurpose
from app.services.observability_service import ObservabilityService
from app.web.routers.api import get_session

router = APIRouter(tags=["usage"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def _window(from_: date | None, to: date | None) -> tuple[datetime, datetime]:
    """FE-20 - the default window is the last 7 days."""
    if to:
        # `to` is inclusive on the screen, so the window runs to the end of that day.
        end = datetime.combine(to, datetime.min.time(), UTC) + timedelta(days=1)
    else:
        end = datetime.now(UTC)
    start = (
        datetime.combine(from_, datetime.min.time(), UTC)
        if from_
        else end - timedelta(days=7)
    )
    if start >= end:
        raise HTTPException(status_code=400, detail="from must be before to")
    return start, end


def _purpose(raw: str | None) -> LlmPurpose | None:
    if not raw:
        return None
    try:
        return LlmPurpose(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"unknown purpose: {raw}") from exc


@router.get("/api/usage")
def usage_json(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    purpose: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    start, end = _window(from_, to)
    return ObservabilityService(session).usage(start, end, _purpose(purpose))


@router.get("/usage", response_class=HTMLResponse)
def usage_page(
    request: Request,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    start, end = _window(from_, to)
    summary = ObservabilityService(session).usage(start, end)
    return templates.TemplateResponse(
        request,
        "usage.html",
        {"active": "usage", "usage": summary},
    )
