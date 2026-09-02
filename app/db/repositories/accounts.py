"""UserRepo - E21 persistence.

No transaction control, like every other repository here: it writes into the
session it was handed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Document, QueryLogRow, UserAccount


def normalise_email(email: str) -> str:
    """BR-132. One place, used by both writes and reads.

    Two normalisations that disagree are the same bug as none at all.
    """
    return (email or "").strip().lower()


class UserRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def by_email(self, email: str) -> UserAccount | None:
        return self._s.scalar(
            select(UserAccount).where(UserAccount.email == normalise_email(email))
        )

    def get(self, user_id: int) -> UserAccount | None:
        return self._s.get(UserAccount, user_id)

    def create(
        self, *, email: str, password_hash: str, disclaimer_version: str
    ) -> UserAccount:
        account = UserAccount(
            email=normalise_email(email),
            password_hash=password_hash,
            disclaimer_version=disclaimer_version,
            disclaimer_agreed_at=datetime.now(UTC),
        )
        self._s.add(account)
        self._s.flush()
        return account

    def record_success(self, account: UserAccount) -> None:
        account.last_login_at = datetime.now(UTC)
        # AP-2 - a successful login clears the delay. Otherwise a user who
        # mistyped four times carries the penalty for the rest of the day.
        account.failed_attempts = 0
        account.last_failed_at = None
        self._s.flush()

    def record_failure(self, account: UserAccount | None) -> None:
        # `None` when the address is not registered: there is nothing to count,
        # and creating a row would turn the login form into a way to enumerate.
        if account is None:
            return
        account.failed_attempts = (account.failed_attempts or 0) + 1
        account.last_failed_at = datetime.now(UTC)
        self._s.flush()

    # ---- quota (UP-4) ----
    def upload_usage(self, owner_id: int) -> tuple[int, int]:
        """(bytes, documents) currently held by this owner.

        Computed, not stored. A running total would need updating on every
        upload, delete and failure path, and the one that gets missed leaves the
        quota silently disagreeing with reality.
        """
        row = self._s.execute(
            select(
                func.coalesce(func.sum(Document.upload_size_bytes), 0),
                func.count(Document.id),
            ).where(Document.owner_id == owner_id)
        ).one()
        return int(row[0] or 0), int(row[1] or 0)

    # ---- history (FR-32) ----
    def query_history(self, owner_id: int, limit: int = 50) -> list[QueryLogRow]:
        return list(
            self._s.scalars(
                select(QueryLogRow)
                .where(QueryLogRow.owner_id == owner_id)
                .order_by(QueryLogRow.asked_at.desc())
                .limit(limit)
            )
        )
