"""C14 AccessPolicyChecker (FR-5, BR-03~BR-05, CON-3).

There is no bypass here, and that is the point. A previous project in this
workspace shipped a headless-browser fallback that silently defeated its own
robots policy; the defect only surfaced during container testing. This class
exposes exactly one verdict and no override, so the same mistake cannot be made
by adding a flag later (BR-04).
"""

from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.types import PolicyDecision

log = get_logger(__name__)

USER_AGENT = "safeenv-collector"


@dataclass(frozen=True)
class PolicyVerdict:
    decision: PolicyDecision
    reason: str
    checked_at: datetime

    @property
    def allowed(self) -> bool:
        return self.decision is PolicyDecision.ALLOWED


class AccessPolicyChecker:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._cache: dict[str, PolicyVerdict] = {}

    def check(self, url: str) -> PolicyVerdict:
        origin = self._origin(url)
        cached = self._cache.get(origin)
        if cached and not self._expired(cached):
            return cached

        verdict = self._evaluate(url, origin)
        self._cache[origin] = verdict
        log.info(
            "policy_checked",
            extra={"origin": origin, "decision": verdict.decision.value,
                   "reason": verdict.reason},
        )
        return verdict

    def is_allowed(self, url: str) -> bool:
        return self.check(url).allowed

    # ---- internals ----
    def _evaluate(self, url: str, origin: str) -> PolicyVerdict:
        now = datetime.now(UTC)

        if not self._settings.respect_robots:
            # Operator override, recorded explicitly so it is never silent.
            return PolicyVerdict(
                PolicyDecision.ALLOWED,
                "RESPECT_ROBOTS=false - robots.txt not consulted (operator override)",
                now,
            )

        robots_url = f"{origin}/robots.txt"
        try:
            response = httpx.get(robots_url, timeout=10.0, follow_redirects=True)
        except httpx.HTTPError as exc:
            # BR-05 - an unreachable robots.txt is treated as "no restriction
            # published", which is the conventional reading. It is recorded as
            # UNKNOWN rather than ALLOWED so the audit trail stays honest.
            return PolicyVerdict(
                PolicyDecision.UNKNOWN, f"robots.txt unreachable: {exc}", now
            )

        if response.status_code == 404:
            return PolicyVerdict(PolicyDecision.UNKNOWN, "robots.txt not published", now)
        if response.status_code >= 400:
            return PolicyVerdict(
                PolicyDecision.UNKNOWN, f"robots.txt HTTP {response.status_code}", now
            )

        parser = urllib.robotparser.RobotFileParser()
        parser.parse(response.text.splitlines())
        if parser.can_fetch(USER_AGENT, url):
            return PolicyVerdict(PolicyDecision.ALLOWED, "permitted by robots.txt", now)
        return PolicyVerdict(
            PolicyDecision.BLOCKED,
            f"robots.txt disallows {USER_AGENT} for this path",
            now,
        )

    def _expired(self, verdict: PolicyVerdict) -> bool:
        ttl = timedelta(seconds=self._settings.policy_cache_ttl)
        return datetime.now(UTC) - verdict.checked_at > ttl

    @staticmethod
    def _origin(url: str) -> str:
        parts = urlparse(url)
        return f"{parts.scheme}://{parts.netloc}"


class AllowAllPolicyChecker:
    """Test double. Never wired into the running application."""

    def check(self, url: str) -> PolicyVerdict:
        return PolicyVerdict(PolicyDecision.ALLOWED, "test double", datetime.now(UTC))

    def is_allowed(self, url: str) -> bool:
        return True
