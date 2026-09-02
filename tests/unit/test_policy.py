"""Access policy — BR-03, BR-04, BR-05, CON-3.

The test that matters most is `test_no_bypass_is_offered`: the previous project
in this workspace shipped a headless-browser fallback that quietly defeated its
own robots policy, and the defect only surfaced during container testing. This
asserts the class has no override surface at all.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core.types import PolicyDecision
from app.ingestion.policy import AccessPolicyChecker, PolicyVerdict


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


@pytest.fixture
def checker(settings, monkeypatch):
    return AccessPolicyChecker(settings)


def _patch_robots(monkeypatch, response):
    def fake_get(url, **kwargs):
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(httpx, "get", fake_get)


class TestVerdicts:
    def test_allowed_when_robots_permits(self, checker, monkeypatch):
        _patch_robots(monkeypatch, _FakeResponse(200, "User-agent: *\nAllow: /\n"))
        verdict = checker.check("https://data.example.test/api/list")
        assert verdict.decision is PolicyDecision.ALLOWED
        assert verdict.allowed is True

    def test_blocked_when_robots_disallows_everything(self, checker, monkeypatch):
        _patch_robots(monkeypatch, _FakeResponse(200, "User-agent: *\nDisallow: /\n"))
        verdict = checker.check("https://blocked.example.test/api/list")
        assert verdict.decision is PolicyDecision.BLOCKED
        assert verdict.allowed is False
        assert "robots.txt" in verdict.reason

    def test_blocked_for_a_specific_path_only(self, checker, monkeypatch):
        _patch_robots(
            monkeypatch, _FakeResponse(200, "User-agent: *\nDisallow: /private/\n")
        )
        assert checker.is_allowed("https://x.example.test/public/a") is True
        checker._cache.clear()  # different path, same origin
        _patch_robots(
            monkeypatch, _FakeResponse(200, "User-agent: *\nDisallow: /private/\n")
        )
        assert checker.is_allowed("https://x.example.test/private/a") is False

    def test_missing_robots_is_unknown_not_allowed(self, checker, monkeypatch):
        """The audit trail should say 'not published', not claim permission."""
        _patch_robots(monkeypatch, _FakeResponse(404))
        verdict = checker.check("https://norobots.example.test/api")
        assert verdict.decision is PolicyDecision.UNKNOWN
        assert verdict.allowed is False

    def test_unreachable_robots_is_unknown(self, checker, monkeypatch):
        _patch_robots(monkeypatch, httpx.ConnectError("dns failure"))
        verdict = checker.check("https://down.example.test/api")
        assert verdict.decision is PolicyDecision.UNKNOWN


class TestNoBypass:
    def test_no_bypass_is_offered(self, checker):
        """BR-04 — there must be no force/override/ignore entry point.

        A verdict is a verdict. If a later change wants an escape hatch, this
        test should be the thing that objects.
        """
        surface = {name for name in dir(checker) if not name.startswith("_")}
        forbidden = {"force", "override", "ignore", "bypass", "allow_anyway"}
        assert surface & forbidden == set()

    def test_verdict_is_immutable(self):
        verdict = PolicyVerdict(PolicyDecision.BLOCKED, "disallowed", datetime.now(UTC))
        with pytest.raises(FrozenInstanceError):
            verdict.decision = PolicyDecision.ALLOWED  # type: ignore[misc]


class TestCaching:
    def test_result_is_cached_per_origin(self, checker, monkeypatch):
        """BR-05 — one robots fetch per origin per TTL."""
        calls = {"n": 0}

        def counting_get(url, **kwargs):
            calls["n"] += 1
            return _FakeResponse(200, "User-agent: *\nAllow: /\n")

        monkeypatch.setattr(httpx, "get", counting_get)
        checker.check("https://cached.example.test/a")
        checker.check("https://cached.example.test/b")
        assert calls["n"] == 1

    def test_expired_entry_is_refetched(self, checker, monkeypatch):
        _patch_robots(monkeypatch, _FakeResponse(200, "User-agent: *\nAllow: /\n"))
        checker.check("https://ttl.example.test/a")
        stale = checker._cache["https://ttl.example.test"]
        checker._cache["https://ttl.example.test"] = PolicyVerdict(
            stale.decision, stale.reason, datetime.now(UTC) - timedelta(days=30)
        )
        calls = {"n": 0}

        def counting_get(url, **kwargs):
            calls["n"] += 1
            return _FakeResponse(200, "User-agent: *\nDisallow: /\n")

        monkeypatch.setattr(httpx, "get", counting_get)
        verdict = checker.check("https://ttl.example.test/a")
        assert calls["n"] == 1
        assert verdict.decision is PolicyDecision.BLOCKED


class TestOverrideSetting:
    def test_respect_robots_false_is_recorded_explicitly(self, settings, monkeypatch):
        """An operator override must never look like a normal 'allowed'."""
        relaxed = settings.model_copy(update={"respect_robots": False})
        checker = AccessPolicyChecker(relaxed)
        verdict = checker.check("https://anything.example.test/a")
        assert verdict.decision is PolicyDecision.ALLOWED
        assert "RESPECT_ROBOTS=false" in verdict.reason
