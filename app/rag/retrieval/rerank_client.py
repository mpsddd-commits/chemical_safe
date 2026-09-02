"""C34 - HTTP client for the reranker container (PP-2, BR-70, BR-71).

Two decisions are worth stating because they look like omissions.

**The timeout equals the reranker's slice of the NFR-2 budget (1,200ms), not
some larger "be generous" value.** A reranker that has already blown the budget
has broken the SLO whether or not we wait for it, so waiting buys a worse answer
*and* a slower one.

**Failure is not an error.** Timeout, connection refused, a malformed response -
all of them fall back to fusion order with a warning (BR-71). The reranker
improves an ordering that is already usable; letting it fail the search would
make an optional component mandatory.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.rag.types import Evidence, RetrievalCandidate

log = get_logger(__name__)


class RerankClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # Process-wide, because every query would otherwise re-learn the same
        # thing at full price.
        self._unavailable_until = 0.0

    @property
    def enabled(self) -> bool:
        return self._settings.reranker_enabled

    def _in_cooldown(self) -> bool:
        return time.monotonic() < self._unavailable_until

    def _begin_cooldown(self) -> None:
        self._unavailable_until = time.monotonic() + self._settings.reranker_cooldown_seconds

    def rerank(
        self, query: str, candidates: list[RetrievalCandidate], texts: dict[int, str]
    ) -> tuple[list[RetrievalCandidate], bool]:
        """Returns (ordered candidates, reranked?).

        The flag is what `query_log.mode` records: claiming `hybrid_reranked`
        after a silent fallback would misattribute the ordering.
        """
        if not self.enabled or not candidates:
            return candidates, False
        if self._in_cooldown():
            # Known down. Skipping is the same outcome as trying and failing,
            # minus the seconds it costs to find out again.
            return candidates, False

        payload = json.dumps(
            {
                "query": query,
                "docs": [texts.get(c.chunk_id, "") for c in candidates],
            }
        ).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310 - fixed internal URL from config
            f"{self._settings.reranker_url.rstrip('/')}/rerank",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout = self._settings.reranker_timeout_ms / 1000
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                scores = json.loads(response.read()).get("scores") or []
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            self._begin_cooldown()
            log.warning(
                "rerank_unavailable_using_fusion_order",
                extra={
                    "error": str(exc),
                    "timeout_ms": self._settings.reranker_timeout_ms,
                    "cooldown_s": self._settings.reranker_cooldown_seconds,
                },
            )
            return candidates, False

        if len(scores) != len(candidates):
            # A length mismatch means we cannot say which score belongs to which
            # candidate. Guessing would silently reorder evidence.
            log.warning(
                "rerank_length_mismatch",
                extra={"expected": len(candidates), "received": len(scores)},
            )
            return candidates, False

        for candidate, score in zip(candidates, scores, strict=True):
            candidate.rerank_score = float(score)
        ordered = sorted(candidates, key=lambda c: (-c.score, c.chunk_id))
        return ordered, True


def evidence_texts(evidence: list[Evidence]) -> dict[int, str]:
    return {item.chunk_id: item.text for item in evidence}
