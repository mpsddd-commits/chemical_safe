"""Usage routes - P6 (FR-42, NFR-19).

The JSON and the HTML view call the same service method, so the two cannot
drift into disagreeing about what a period cost (DD-12).

**B2 - `/usage` is admin-only.** Measured before the change: this route carried
no authentication dependency at all - not `require_user`, not even
`current_user` - so it was the one screen where anonymous access was not a
policy choice that had been made loosely, but a question nobody had asked. The
u5 documents describing it as "login only" were describing an intention, not
the code. Loopback binding (NFR-18) was the only actual control.

The guard is on the handler rather than the router because this router is not
all one thing: `/api/usage` lives here too and is **deliberately left open in
this commit**, because the B-group design scoped B2 to `/usage` and B2a to the
`prefix="/api"` router in `api.py`, and `/api/usage` is in neither. It is
recorded here rather than fixed quietly: it serves the same numbers as the
screen above it, so as of this commit the period cost is still readable by an
anonymous caller who asks for JSON. Closing it is a decision for whoever owns
the B-group scope, not a change to make on the way past.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.types import AuthenticatedUser
from app.core.types import LlmPurpose
from app.services.observability_service import ObservabilityService
from app.web.deps import require_admin
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
    user: AuthenticatedUser = Depends(require_admin),
) -> HTMLResponse:
    start, end = _window(from_, to)
    summary = ObservabilityService(session).usage(start, end)
    return templates.TemplateResponse(
        request,
        "usage.html",
        # B2 - `user` alongside the flag. B3 passed `is_admin` from
        # `admin_flag` and nothing else, which rendered an admin the signed-out
        # banner and a "로그인" link under a navigation only admins can see.
        # `is_admin` is a literal now for the same reason as in `admin.py`:
        # `require_admin` has already answered it for this request, and asking
        # `admin_flag` again would open a second session to re-derive it.
        {"active": "usage", "usage": summary, "user": user, "is_admin": True},
    )
