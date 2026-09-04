"""Request-scoped dependencies for u5 - authentication and CSRF.

**Two user dependencies, not one.** `current_user` allows anonymous and may
return `None`; `require_user` redirects to the login page. They exist as a pair
because BR-151 keeps the query and substance screens open while documents and
history are not, and a single dependency would have to pick a default that is
wrong for one half - either new screens are unprotected, or the public query
disappears.

Middleware was the alternative and it needs an exemption list, which is a list
that gets forgotten every time a screen is added.

B3 adds a third, `require_admin`, for the screens where "has an account" was
never the question being asked. B2a adds a fourth, `require_admin_api`, which
is the same rule with the JSON answer instead of the redirect - see its
docstring for why the redirect could not simply be reused.
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
from app.core.types import Role
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


def is_admin(session: Session, user: AuthenticatedUser | None) -> bool:
    """Does this request belong to an admin? One SELECT, or none for anonymous.

    Split out of `require_admin` because the navigation needs the same answer
    without the 403: a link nobody may follow is worse than no link.
    """
    if user is None:
        return False
    from app.db.repositories.accounts import UserRepo

    account = UserRepo(session).get(user.id)
    # A token for an account that has since been deleted is not an admin. It is
    # also not a login prompt - `require_user` already accepted the token, and
    # the row is simply gone.
    return account is not None and account.role == Role.ADMIN


def require_admin(
    user: AuthenticatedUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> AuthenticatedUser:
    """B3 - logged in *and* an admin.

    Two decisions worth keeping.

    **403, not a redirect.** `require_user` runs first, so reaching this line
    means the login already happened. Sending them to `/login` would show a
    signed-in person a login form, they would sign in again, and land back
    here - a loop whose exit is clearing the cookie. 403 says the true thing:
    the identity is known and it is not allowed.

    **The role is read from the database, never from the token.** Measured:
    `current_user` verifies the JWT and touches no database, so a role carried
    in the payload would stay valid until the token expires - up to 12 hours
    (`jwt_expire_hours`). That is AP-3's known cost, accepted for identity
    because a stolen token is an incident either way; it is not acceptable for
    *revocation*, where the whole point is that `revoke-admin` takes effect on
    the next request. The admin screens are a handful of low-traffic pages, so
    one SELECT per request is cheaper than a demotion that does not demote.

    `AuthenticatedUser` is deliberately left alone. It is built from the token
    and nothing else; hanging a role on it would create a field that is filled
    on the routes that happen to look it up and empty everywhere else, and the
    next reader could not tell "not an admin" from "nobody asked".
    """
    if not is_admin(session, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    return user


def require_admin_api(
    user: AuthenticatedUser | None = Depends(current_user),
    session: Session = Depends(get_session),
) -> AuthenticatedUser:
    """B2a - `require_admin` for JSON routes: 401 when anonymous, 403 when not admin.

    It does not go through `require_user`, and that is the whole point.
    `require_user` raises `LoginRequired`, which `create_app` turns into a
    **303 to `/login`**. Measured against the running container: a client that
    follows redirects (`curl -L`, `httpx(follow_redirects=True)`, browser
    `fetch`) then receives the login page with status **200 and an HTML body**.
    So "you are not authenticated" arrives at a JSON caller as a successful
    response containing `<!doctype html>` - the caller has to sniff the body to
    tell refusal from data. That is how `/api/sources` read as "anonymous 200"
    in the exposure survey in the first place; a redirect here would keep the
    same shape and only move where the HTML comes from.

    401 vs 403 is kept as two distinct answers because the caller's next move
    differs: 401 means "send a session cookie", 403 means "this cookie will
    never be enough, stop retrying". Collapsing both into 403 would have a
    signed-out script retry forever; collapsing both into 401 would have a
    signed-in non-admin re-authenticate to no effect.

    No `WWW-Authenticate` header: the scheme here is a session cookie issued by
    the HTML login form, not a challenge the client can answer in-band, and a
    `Basic` challenge would pop a browser dialog that cannot log anyone in.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
        )
    if not is_admin(session, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    return user


def admin_flag(user: AuthenticatedUser | None = Depends(current_user)) -> bool:
    """`is_admin` for a template context, as a dependency the screens can take.

    It opens its own session instead of taking `get_session`, for one reason:
    `Depends(get_session)` would open a transaction on **every** page render,
    and the busiest page here is the anonymous query screen, which today needs
    no database session at all. Anonymous short-circuits before any connection
    is asked for. A second concurrent session for signed-in users is the same
    shape as `observability_scope` in the query path, which is already here.

    Navigation only. It hides links; it does not guard routes - `require_admin`
    does that, and a hidden link is not a control.
    """
    if user is None:
        return False
    with session_scope() as session:
        return is_admin(session, user)


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
