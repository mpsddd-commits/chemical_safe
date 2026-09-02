"""N5 PricingTable - CP-1, BR-96, NFR-19.

Returns ``None``, never ``0``, for a model it has no price for. That distinction
is the whole reason this module exists: zero and unknown look identical in a
total, and a usage screen that reports an unpriced call as free is not merely
imprecise, it is wrong in the direction that hides money (NFR-8).

This supersedes u1's hard-coded `_RATES` table in `adapters/tracing.py`, which
returned 0.0 for unknown models - harmless while nothing called an LLM, exactly
the failure BR-96 forbids once something does.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.logging import get_logger

log = get_logger(__name__)

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "llm_pricing.yaml"
_PER_MILLION = Decimal(1_000_000)


class PricingTable:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_PATH
        self._rates: dict[str, dict[str, Decimal]] | None = None

    def _load(self) -> dict[str, dict[str, Decimal]]:
        if self._rates is not None:
            return self._rates
        if not self._path.exists():
            # Not fatal. Missing prices degrade to "cost unknown", which the
            # usage view can state honestly; refusing to answer queries because
            # a price list is absent would be the wrong trade.
            log.warning("pricing_table_missing", extra={"path": str(self._path)})
            self._rates = {}
            return self._rates
        raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        self._rates = {
            str(model): {str(k): Decimal(str(v)) for k, v in (values or {}).items()}
            for model, values in raw.items()
        }
        return self._rates

    def has(self, model: str) -> bool:
        return model in self._load()

    def cost_for(
        self,
        model: str,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        cache_read_tokens: int | None = None,
    ) -> Decimal | None:
        """USD for one call, or None when the model has no registered price.

        Cache reads are billed separately and cheaply; when a rate for them is
        absent they fall back to the input rate rather than being dropped, since
        dropping them would understate the bill.
        """
        rates = self._load().get(model)
        if rates is None:
            return None

        in_rate = rates.get("input_per_1m", Decimal(0))
        out_rate = rates.get("output_per_1m", Decimal(0))
        cache_rate = rates.get("cache_read_per_1m", in_rate)

        total = (
            Decimal(input_tokens or 0) * in_rate
            + Decimal(output_tokens or 0) * out_rate
            + Decimal(cache_read_tokens or 0) * cache_rate
        ) / _PER_MILLION
        return total.quantize(Decimal("0.000001"))


@lru_cache(maxsize=1)
def shared_pricing() -> PricingTable:
    return PricingTable()
