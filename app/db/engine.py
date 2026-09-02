"""C3 Database — engine, session and transaction boundaries.

Domain components never receive a Session; they go through repositories (DD-20)
so that business logic can be unit-tested without a database (NFR-24, NFR-28).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_engine(settings: Settings | None = None) -> Engine:
    global _engine, _session_factory
    settings = settings or get_settings()
    settings.require_db_password()
    _engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        return init_engine()
    return _engine


def set_session_factory(factory: sessionmaker[Session]) -> None:
    """Test seam — lets the suite install an in-memory factory."""
    global _session_factory
    _session_factory = factory


@contextmanager
def observability_scope() -> Iterator[Session]:
    """A session whose commits do **not** share the fate of the work observed.

    `session_scope` rolls the whole transaction back on an exception, which is
    right for the answer content (BR-92: sentences, citations and snapshots
    commit together or not at all). It is wrong for the record *that* a query
    ran: measured 2026-08-25, a failed query left no `query_log` row and no
    `llm_call` rows, so observability disappeared at exactly the moment it was
    needed and BR-78 ("a refusal is recorded") and BR-95 ("failed calls are
    recorded too") were unreachable on the error path.

    Same engine, separate transaction. The caller commits explicitly at the
    points where a fact becomes worth keeping.
    """
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
    finally:
        try:
            session.commit()
        except Exception:  # noqa: BLE001 - observability must not mask the real error
            session.rollback()
            log.warning("observability_commit_failed", exc_info=True)
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """One transaction. Ingestion uses one document per transaction (DD-24, BR-53)."""
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_extensions() -> None:
    """pgvector must be present before the vector column can be used (DD-15)."""
    with get_engine().begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def check_connection() -> bool:
    """Used by the health check (FR-43)."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - health check must not raise
        log.warning("db_health_check_failed", extra={"error": str(exc)})
        return False
