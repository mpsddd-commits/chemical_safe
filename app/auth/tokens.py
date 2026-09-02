"""C52 TokenService - FR-31, NFR-12, BR-135~BR-137.

Stateless. A logout deletes the cookie and nothing else, which is the honest
description of what this gives you: **a stolen token stays valid until it
expires, at most 12 hours.** A blocklist would close that, at the cost of a
state lookup on every request, and this file does not pretend to have one.

The signing key has no default (BR-137). A development default travels to
deployment, and a key with a default is not a key.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from app.auth.types import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

ALGORITHM = "HS256"
COOKIE_NAME = "safeenv_session"


class TokenService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # Fail here, not on the first login: a system that authenticates must
        # not start without a signing key.
        self._settings.require_jwt_secret()

    @property
    def _key(self) -> str:
        return self._settings.jwt_secret.get_secret_value()

    @property
    def max_age_seconds(self) -> int:
        return self._settings.jwt_expire_hours * 3600

    def issue(self, user_id: int, email: str) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=self._settings.jwt_expire_hours)).timestamp()),
        }
        return jwt.encode(payload, self._key, algorithm=ALGORITHM)

    def verify(self, token: str | None) -> AuthenticatedUser | None:
        """Every failure is `None`.

        Expired, tampered, malformed, absent - the caller has the same thing to
        do in each case, and distinguishing them only creates a response that
        describes the token to whoever supplied it.
        """
        if not token:
            return None
        try:
            payload = jwt.decode(token, self._key, algorithms=[ALGORITHM])
        except jwt.PyJWTError:
            return None
        subject = payload.get("sub")
        email = payload.get("email")
        if not subject or not email:
            return None
        try:
            user_id = int(subject)
        except (TypeError, ValueError):
            return None
        return AuthenticatedUser(id=user_id, email=str(email))
