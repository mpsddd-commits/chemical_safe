"""P8 - registration, login, logout (FR-31, FR-33, FR-34).

Server-rendered forms, like every other screen here. No JavaScript is required
to sign in, which is the same commitment u1 made for the rest of the app (DD-17).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.types import AuthenticatedUser
from app.core.config import get_settings
from app.core.errors import AuthenticationError, ValidationError
from app.core.logging import get_logger
from app.services.account_service import AccountService
from app.web.deps import (
    clear_auth_cookie,
    current_user,
    get_session,
    issue_csrf,
    set_auth_cookie,
    set_csrf_cookie,
    verify_csrf,
)

log = get_logger(__name__)
router = APIRouter(tags=["auth"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

SAFE_NEXT_PREFIX = "/"


def _safe_next(value: str | None) -> str:
    """Only same-site paths.

    An open redirect turns the login page into a way to send someone to another
    host with our name on the link.
    """
    if not value or not value.startswith(SAFE_NEXT_PREFIX) or value.startswith("//"):
        return "/"
    return value


def _render(request: Request, template: str, **context) -> HTMLResponse:
    token = issue_csrf(request)
    response = templates.TemplateResponse(
        request,
        template,
        {"active": "auth", "csrf_token": token, **context},
        status_code=context.pop("status_code", 200),
    )
    set_csrf_cookie(response, token)
    return response


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request, user: AuthenticatedUser | None = Depends(current_user)
) -> HTMLResponse:
    if user is not None:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return _render(request, "login.html", next=_safe_next(request.query_params.get("next")))


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    csrf_token: str = Form(""),
    session: Session = Depends(get_session),
):
    verify_csrf(request, csrf_token)
    try:
        _user, token = AccountService(session).login(email, password)
    except AuthenticationError as exc:
        # One message for both causes (BR-134). The email is echoed back so the
        # person does not retype it; the password never is.
        return _render(
            request, "login.html", email=email, next=next, error=str(exc), status_code=401
        )
    response = RedirectResponse(_safe_next(next), status_code=status.HTTP_303_SEE_OTHER)
    set_auth_cookie(response, token)
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(
    request: Request, user: AuthenticatedUser | None = Depends(current_user)
) -> HTMLResponse:
    if user is not None:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return _render(
        request, "register.html", disclaimer_version=get_settings().disclaimer_version
    )


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    agree: str = Form(""),
    csrf_token: str = Form(""),
    session: Session = Depends(get_session),
):
    verify_csrf(request, csrf_token)
    try:
        # Checked here as well as in the form. A checkbox validated only in the
        # browser is guidance, not a requirement (BR-152).
        _user, token = AccountService(session).register(
            email, password, disclaimer_agreed=agree == "on"
        )
    except ValidationError as exc:
        return _render(
            request,
            "register.html",
            email=email,
            error=str(exc),
            disclaimer_version=get_settings().disclaimer_version,
            status_code=400,
        )
    response = RedirectResponse("/documents", status_code=status.HTTP_303_SEE_OTHER)
    set_auth_cookie(response, token)
    return response


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form("")):
    verify_csrf(request, csrf_token)
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    clear_auth_cookie(response)
    return response
