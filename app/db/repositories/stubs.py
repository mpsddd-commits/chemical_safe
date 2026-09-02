"""Repository stubs for units that have not been built yet.

`UserRepo`, `QueryLogRepo` and `EvaluationRepo` are declared now so that the
repository surface named in the Application Design (C4, eight repositories) is
complete and importable. Their tables arrive with the u2 / u4 / u5 migrations.

Calling any method raises rather than silently returning empty data - a stub
that lies is worse than one that fails loudly.
"""

from __future__ import annotations

from sqlalchemy.orm import Session


class _NotYetImplementedRepo:
    _unit = "?"

    def __init__(self, session: Session) -> None:
        self._s = session

    def _fail(self, method: str):
        raise NotImplementedError(
            f"{type(self).__name__}.{method} is delivered in unit {self._unit}."
        )


class UserRepo(_NotYetImplementedRepo):
    """u5 - accounts (FR-31~33)."""

    _unit = "u5-account-upload"

    def get_by_email(self, email: str):
        self._fail("get_by_email")

    def create(self, email: str, password_hash: str):
        self._fail("create")


class QueryLogRepo(_NotYetImplementedRepo):
    """u2 - query history (FR-32)."""

    _unit = "u2-rag-qa"

    def save(self, **fields: object):
        self._fail("save")

    def list_for_user(self, user_id: int, limit: int = 20, offset: int = 0):
        self._fail("list_for_user")


class EvaluationRepo(_NotYetImplementedRepo):
    """u4 - evaluation runs (FR-36~39)."""

    _unit = "u4-evaluation"

    def save_run(self, **fields: object):
        self._fail("save_run")

    def list_runs(self, limit: int = 20):
        self._fail("list_runs")
