"""Request-scoped dependencies for u5 - authentication and CSRF.

**Two user dependencies, not one.** `current_user` allows anonymous and may
return `None`; `require_user` redirects to the login page. They exist as a pair
because BR-151 keeps the query and substance screens open while documents and
history are not, and a single dependency would have to pick a default that is
wrong for one half - either new screens are unprotected, or the public query
disappears.

Middleware was the alternative and it needs an exemption list, which is a list
that gets forgotten every time a screen is added.
"""

from __future__ import annotations

import hmac
import secrets
from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.tokens import COOKIE_NAME, TokenService
from app.auth.types import AuthenticatedUser
from app.core.config import get_settings
from app.db.engine import session_scope

CSRF_COOKIE = "safeenv_csrf"
CSRF_FIELD = "csrf_token"


def get_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session


def current_user(request: Request) -> AuthenticatedUser | None:
    """Anonymous is a valid answer, not a failure (BR-151)."""
    # No try/except around the signing key: `create_app` refuses to start
    # without one (BR-137), so a missing key cannot reach here. Swallowing it
    # would turn a misconfiguration into "everyone is anonymous", which looks
    # like the app working.
    return TokenService().verify(request.cookies.get(COOKIE_NAME))


class LoginRequired(HTTPException):
    """Carries the redirect instead of a body — these are SSR screens."""

    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_303_SEE_OTHER, detail="login required")


def require_user(
    user: AuthenticatedUser | None = Depends(current_user),
) -> AuthenticatedUser:
    if user is None:
        raise LoginRequired()
    return user


def login_redirect(request: Request) -> RedirectResponse:
    nxt = request.url.path
    return RedirectResponse(url=f"/login?next={nxt}", status_code=status.HTTP_303_SEE_OTHER)


# ---- CSRF (AP-4, BR-138) ----
#
# SameSite=Lax blocks cross-site POSTs, but it is a defence that lives in the
# browser. Deletion and upload cannot be undone, so the server keeps something
# it can check itself.


def issue_csrf(request: Request) -> str:
    existing = request.cookies.get(CSRF_COOKIE)
    return existing or secrets.token_urlsafe(32)


def verify_csrf(request: Request, submitted: str | None) -> None:
    expected = request.cookies.get(CSRF_COOKIE)
    # `compare_digest` rather than `==`: the comparison is over a secret, and a
    # short-circuiting compare leaks its prefix through timing.
    if not expected or not submitted or not hmac.compare_digest(expected, submitted):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="요청이 만료되었거나 올바르지 않습니다. 다시 시도하세요.",
        )


def set_auth_cookie(response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.jwt_expire_hours * 3600,
        # HttpOnly is the whole reason the token lives in a cookie: JavaScript
        # cannot read it, so one XSS is not an account takeover (BR-135).
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def set_csrf_cookie(response, value: str) -> None:
    settings = get_settings()
    # Readable by the template renderer only - it is embedded in forms server
    # side, so it does not need to be readable by JavaScript either.
    response.set_cookie(
        CSRF_COOKIE,
        value,
        max_age=get_settings().jwt_expire_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_auth_cookie(response) -> None:
    """Logout is this and nothing else (AP-3).

    A token already copied elsewhere stays valid until it expires - at most 12
    hours. There is no server-side revocation and this file does not imply one.
    """
    response.delete_cookie(COOKIE_NAME, path="/")
