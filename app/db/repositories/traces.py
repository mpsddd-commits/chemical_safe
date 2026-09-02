"""LlmCallRepo - E18, the real table u1's in-memory `TraceRepo` stood in for.

Failed calls are recorded too (BR-95). A usage view built only from successes
understates what was actually spent, and the failures are exactly what you want
to see when the bill looks wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import LlmPurpose
from app.db.models import LlmCallRow


@dataclass
class UsageSummary:
    """W11 output.

    `unpriced_calls` travels with `cost_usd` on purpose. A total shown alone
    reads as "this is everything"; when unpriced calls are mixed in, that is not
    true, and the screen must not be able to omit the caveat (BR-96).
    """

    calls: int
    ok_calls: int
    failed_calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    cost_usd: Decimal | None
    unpriced_calls: int
    by_purpose: list[dict]
    by_model: list[dict]


class LlmCallRepo:
    def __init__(self, session: Session) -> None:
        self._s = session

    def record(
        self,
        *,
        purpose: LlmPurpose,
        provider: str,
        model: str,
        latency_ms: int,
        ok: bool,
        query_id: int | None = None,
        prompt_name: str | None = None,
        prompt_version: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cache_read_tokens: int | None = None,
        cost_usd: Decimal | None = None,
        stop_reason: str | None = None,
        error_kind: str | None = None,
    ) -> LlmCallRow:
        row = LlmCallRow(
            query_id=query_id,
            purpose=purpose.value,
            provider=provider,
            model=model,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            latency_ms=latency_ms,
            # None stays None. Never coerced to 0 (BR-96).
            cost_usd=cost_usd,
            ok=ok,
            stop_reason=stop_reason,
            error_kind=error_kind,
        )
        self._s.add(row)
        return row

    def summarise(
        self, start: datetime, end: datetime, purpose: LlmPurpose | None = None
    ) -> UsageSummary:
        window = [LlmCallRow.called_at >= start, LlmCallRow.called_at < end]
        if purpose:
            window.append(LlmCallRow.purpose == purpose.value)

        totals = self._s.execute(
            select(
                func.count(),
                func.count().filter(LlmCallRow.ok.is_(True)),
                func.coalesce(func.sum(LlmCallRow.input_tokens), 0),
                func.coalesce(func.sum(LlmCallRow.output_tokens), 0),
                func.coalesce(func.sum(LlmCallRow.cache_read_tokens), 0),
                func.percentile_disc(0.5).within_group(LlmCallRow.latency_ms),
                func.percentile_disc(0.95).within_group(LlmCallRow.latency_ms),
                func.sum(LlmCallRow.cost_usd),
                # Priced-but-null is the caveat; the count travels with the sum.
                func.count().filter(LlmCallRow.cost_usd.is_(None)),
            ).where(*window)
        ).one()

        by_purpose = [
            {"purpose": p, "calls": c, "cost_usd": cost, "unpriced": unpriced}
            for p, c, cost, unpriced in self._s.execute(
                select(
                    LlmCallRow.purpose,
                    func.count(),
                    func.sum(LlmCallRow.cost_usd),
                    func.count().filter(LlmCallRow.cost_usd.is_(None)),
                )
                .where(*window)
                .group_by(LlmCallRow.purpose)
                .order_by(func.count().desc())
            )
        ]
        by_model = [
            {"model": m, "calls": c, "cost_usd": cost, "unpriced": unpriced}
            for m, c, cost, unpriced in self._s.execute(
                select(
                    LlmCallRow.model,
                    func.count(),
                    func.sum(LlmCallRow.cost_usd),
                    func.count().filter(LlmCallRow.cost_usd.is_(None)),
                )
                .where(*window)
                .group_by(LlmCallRow.model)
                .order_by(func.count().desc())
            )
        ]

        calls, ok_calls, inp, out, cached, p50, p95, cost, unpriced = totals
        return UsageSummary(
            calls=calls,
            ok_calls=ok_calls,
            failed_calls=calls - ok_calls,
            input_tokens=int(inp),
            output_tokens=int(out),
            cache_read_tokens=int(cached),
            latency_p50_ms=int(p50) if p50 is not None else None,
            latency_p95_ms=int(p95) if p95 is not None else None,
            cost_usd=cost,
            unpriced_calls=unpriced,
            by_purpose=by_purpose,
            by_model=by_model,
        )

    def cache_hit_ratio(self, start: datetime, end: datetime) -> float | None:
        """PP-4 - the only way to see whether BR-94's prompt layout still works.

        A sustained 0% means the cached prefix is being broken on every request,
        which is a regression even though nothing errors.
        """
        total_in, cached = self._s.execute(
            select(
                func.coalesce(func.sum(LlmCallRow.input_tokens), 0),
                func.coalesce(func.sum(LlmCallRow.cache_read_tokens), 0),
            ).where(LlmCallRow.called_at >= start, LlmCallRow.called_at < end)
        ).one()
        if not total_in:
            return None
        return float(cached) / float(total_in)
