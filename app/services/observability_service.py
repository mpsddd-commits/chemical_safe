"""S8 ObservabilityService - workflows W10 and W11 (FR-41, FR-42, NFR-19).

The summary always carries `unpriced_calls` next to `cost_usd`, and the two
cannot be separated by a caller (BR-96). A total presented alone reads as "this
is everything"; with unpriced calls mixed in that is false, and the screen must
not be able to omit the caveat by accident.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.types import LlmPurpose
from app.db.repositories.queries import QueryRepo
from app.db.repositories.traces import LlmCallRepo, UsageSummary


class ObservabilityService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._s = session
        self._settings = settings or get_settings()
        self._traces = LlmCallRepo(session)
        self._queries = QueryRepo(session)

    def usage(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        purpose: LlmPurpose | None = None,
    ) -> dict:
        end = end or datetime.now(UTC)
        start = start or (end - timedelta(days=7))  # FE-20 default window
        summary: UsageSummary = self._traces.summarise(start, end, purpose)
        return {
            "from": start,
            "to": end,
            "calls": summary.calls,
            "ok_calls": summary.ok_calls,
            "failed_calls": summary.failed_calls,
            "input_tokens": summary.input_tokens,
            "output_tokens": summary.output_tokens,
            "cache_read_tokens": summary.cache_read_tokens,
            # PP-4 - a sustained 0% means BR-94's cached prefix is being broken
            # on every request. Nothing errors, so this number is the only signal.
            "cache_hit_ratio": self._traces.cache_hit_ratio(start, end),
            "latency_p50_ms": summary.latency_p50_ms,
            "latency_p95_ms": summary.latency_p95_ms,
            "cost_usd": summary.cost_usd,
            "unpriced_calls": summary.unpriced_calls,
            "by_purpose": summary.by_purpose,
            "by_model": summary.by_model,
        }

    def purge_expired_queries(self) -> int:
        """FQ3-16 / NFR-14 - questions may be personal and do not live forever."""
        return self._queries.purge_expired(self._settings.query_log_retention_days)
