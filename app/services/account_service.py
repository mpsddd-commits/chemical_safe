"""S6 AccountService - FR-31~34, FR-47.

Registration, login, and the query history a signed-in user can re-read.

The login path is where most of the care goes. Two things are true at once: it
must tell a legitimate user nothing useful when they mistype, and it must not
tell an attacker whether an address is registered - not through the message, and
not through how long the answer takes (BR-134, AP-1).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.auth import hashing
from app.auth.tokens import TokenService
from app.auth.types import AuthenticatedUser
from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError, ValidationError
from app.core.logging import get_logger
from app.db.repositories.accounts import UserRepo, normalise_email

log = get_logger(__name__)

_EMAIL_MIN = 5


@dataclass
class HistoryEntry:
    query_id: int
    question: str
    outcome: str
    asked_at: datetime
    sentence_count: int
    citation_count: int


class AccountService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._s = session
        self._settings = settings or get_settings()
        self._users = UserRepo(session)
        self._tokens = TokenService(self._settings)

    # ---- W19 register ----
    def register(
        self, email: str, password: str, *, disclaimer_agreed: bool
    ) -> tuple[AuthenticatedUser, str]:
        email = normalise_email(email)
        if len(email) < _EMAIL_MIN or "@" not in email:
            raise ValidationError("올바른 이메일 주소를 입력하세요.")
        if not disclaimer_agreed:
            # BR-152 - FR-34 says consent is required before use, so an account
            # cannot come into existence without it.
            raise ValidationError("면책 고지에 동의해야 가입할 수 있습니다.")
        hashing.validate_policy(password)
        if self._users.by_email(email) is not None:
            # Registration has to reveal this - it cannot create a duplicate
            # silently. The login path is where the leak is closed (BR-134).
            raise ValidationError("이미 가입된 이메일입니다.")

        account = self._users.create(
            email=email,
            password_hash=hashing.hash_password(password),
            disclaimer_version=self._settings.disclaimer_version,
        )
        log.info("account_registered", extra={"user_id": account.id})
        user = AuthenticatedUser(id=account.id, email=account.email)
        return user, self._tokens.issue(account.id, account.email)

    # ---- W20 login ----
    def login(self, email: str, password: str) -> tuple[AuthenticatedUser, str]:
        account = self._users.by_email(email)
        self._apply_backoff(account)

        # Verified even when `account is None`, against a dummy hash. Skipping it
        # would make a missing address answer measurably faster than a wrong
        # password, which is the same disclosure the message avoids.
        stored = account.password_hash if account else None
        if not hashing.verify_password(password, stored):
            self._users.record_failure(account)
            log.info("login_failed", extra={"user_id": account.id if account else None})
            raise AuthenticationError("이메일 또는 비밀번호가 올바르지 않습니다.")

        assert account is not None  # verify_password returns False without one
        self._users.record_success(account)
        log.info("login_succeeded", extra={"user_id": account.id})
        user = AuthenticatedUser(id=account.id, email=account.email)
        return user, self._tokens.issue(account.id, account.email)

    def _apply_backoff(self, account) -> None:
        """AP-2 - delay, never lock.

        A lockout would let anyone who knows an address deny that account
        service, which turns the defence into the attack. This only slows the
        attempt rate down, and **that is all it does** - a distributed or
        low-frequency attempt walks past it.
        """
        if account is None or (account.failed_attempts or 0) < self._settings.login_backoff_after:
            return
        over = account.failed_attempts - self._settings.login_backoff_after
        delay = min(2.0**over, self._settings.login_backoff_max_seconds)
        log.info(
            "login_backoff",
            extra={"user_id": account.id, "attempts": account.failed_attempts,
                   "delay_s": delay},
        )
        time.sleep(delay)

    # ---- token ----
    def current_user(self, token: str | None) -> AuthenticatedUser | None:
        return self._tokens.verify(token)

    @property
    def cookie_max_age(self) -> int:
        return self._tokens.max_age_seconds

    # ---- W24 history (FR-32, FR-47) ----
    def query_history(self, user: AuthenticatedUser, limit: int = 50) -> list[HistoryEntry]:
        """Only this user's questions (BR-149).

        Anonymous queries have `owner_id IS NULL` and belong to nobody, so they
        never appear here. That is BR-151's cost, and it is a design decision
        rather than a gap.
        """
        from sqlalchemy import func, select

        from app.db.models import AnswerCitationRow, AnswerSentenceRow

        entries: list[HistoryEntry] = []
        for row in self._users.query_history(user.id, limit):
            sentences = self._s.scalar(
                select(func.count())
                .select_from(AnswerSentenceRow)
                .where(AnswerSentenceRow.query_id == row.id)
            ) or 0
            citations = self._s.scalar(
                select(func.count())
                .select_from(AnswerCitationRow)
                .join(
                    AnswerSentenceRow,
                    AnswerSentenceRow.id == AnswerCitationRow.sentence_id,
                )
                .where(AnswerSentenceRow.query_id == row.id)
            ) or 0
            entries.append(
                HistoryEntry(
                    query_id=row.id,
                    question=row.question,
                    outcome=row.outcome,
                    asked_at=row.asked_at or datetime.now(UTC),
                    sentence_count=int(sentences),
                    citation_count=int(citations),
                )
            )
        return entries
