"""Policy audit trail records what a job enforced - D8, CON-3.

Enforcement was already per document URL and per origin. What these tests pin
is the record: one `policy_check` row per document origin per job, blocked
hosts included, without changing what gets fetched.

The real `AccessPolicyChecker` is used so its per-origin cache is the thing
being deduplicated against; `httpx.get` is replaced, so no robots.txt request
leaves the machine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import urlparse

import httpx
import pytest

from app.core.errors import FailureKind
from app.core.types import JobKind, PolicyCheckScope, PolicyDecision
from app.db.repositories.catalog import SourceRepo
from app.ingestion.change_detector import ChangeDetector
from app.ingestion.orchestrator import IngestionOrchestrator
from app.ingestion.policy import AccessPolicyChecker, PolicyVerdict
from app.ingestion.policy_audit import PolicyVerdictRecorder
from app.jobs.tracker import JobTracker
from tests.unit.test_job_tracker import FakeJobRepo
from tests.unit.test_orchestrator import StubAdapter, _ref

ALLOWING = "https://vendor-a.example.test"
MISSING = "https://vendor-b.example.test"
BLOCKING = "https://vendor-c.example.test"


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


@pytest.fixture
def robots_calls(monkeypatch) -> list[str]:
    calls: list[str] = []
    responses = {
        f"{ALLOWING}/robots.txt": _FakeResponse(200, "User-agent: *\nAllow: /\n"),
        f"{MISSING}/robots.txt": _FakeResponse(404),
        f"{BLOCKING}/robots.txt": _FakeResponse(200, "User-agent: *\nDisallow: /\n"),
    }

    def fake_get(url, **kwargs):
        calls.append(url)
        return responses[url]

    monkeypatch.setattr(httpx, "get", fake_get)
    return calls


@pytest.fixture
def tracker() -> JobTracker:
    return JobTracker(FakeJobRepo())


def _refs():
    """Seven documents on three hosts - none of them the source's base_url."""
    return [
        _ref(1, f"{ALLOWING}/msds/1.pdf"),
        _ref(2, f"{ALLOWING}/msds/2.pdf"),
        _ref(3, f"{ALLOWING}/msds/3.pdf"),
        _ref(4, f"{MISSING}/files/4.pdf"),
        _ref(5, f"{MISSING}/files/5.pdf"),
        _ref(6, f"{BLOCKING}/pdf/6.pdf"),
        _ref(7, f"{BLOCKING}/pdf/7.pdf"),
    ]


def _run(orchestrator: IngestionOrchestrator, job_id: int):
    return orchestrator.run(job_id, None, lambda ref: None, lambda raw: 1)


def _build(adapter, tracker, settings, checker, rows):
    recorder = PolicyVerdictRecorder(lambda job, origin, v: rows.append((job, origin, v)))
    return IngestionOrchestrator(
        adapter,
        tracker,
        checker,
        ChangeDetector(),
        settings=settings,
        sleep=lambda _s: None,
        recorder=recorder,
    )


class TestOneRowPerOrigin:
    def test_each_host_is_recorded_once(self, tracker, settings, robots_calls):
        rows: list = []
        adapter = StubAdapter(_refs())
        job_id = tracker.create(JobKind.INGEST, {})
        _run(_build(adapter, tracker, settings, AccessPolicyChecker(settings), rows), job_id)

        assert sorted(origin for _, origin, _ in rows) == [ALLOWING, MISSING, BLOCKING]
        assert {job for job, _, _ in rows} == {job_id}
        # The cache is what kept it to three: one robots.txt fetch per host.
        assert len(robots_calls) == 3

    def test_decisions_are_the_ones_enforced(self, tracker, settings, robots_calls):
        rows: list = []
        adapter = StubAdapter(_refs())
        job_id = tracker.create(JobKind.INGEST, {})
        _run(_build(adapter, tracker, settings, AccessPolicyChecker(settings), rows), job_id)

        decisions = {origin: v.decision for _, origin, v in rows}
        assert decisions == {
            ALLOWING: PolicyDecision.ALLOWED,
            MISSING: PolicyDecision.UNKNOWN,
            BLOCKING: PolicyDecision.BLOCKED,
        }


class TestJobBoundary:
    def test_same_job_rerun_does_not_record_again(self, tracker, settings, robots_calls):
        rows: list = []
        adapter = StubAdapter(_refs())
        job_id = tracker.create(JobKind.INGEST, {})
        orchestrator = _build(adapter, tracker, settings, AccessPolicyChecker(settings), rows)
        _run(orchestrator, job_id)
        _run(orchestrator, job_id)
        assert len(rows) == 3

    def test_a_later_job_records_its_own_rows(self, tracker, settings, robots_calls):
        """Even from a cached verdict - the question is what *this* run enforced."""
        rows: list = []
        checker = AccessPolicyChecker(settings)
        orchestrator = _build(StubAdapter(_refs()), tracker, settings, checker, rows)
        first = tracker.create(JobKind.INGEST, {})
        second = tracker.create(JobKind.INGEST, {})
        _run(orchestrator, first)
        _run(orchestrator, second)

        assert len(robots_calls) == 3  # second job was served from the cache
        assert sorted((job, origin) for job, origin, _ in rows) == sorted(
            [(first, o) for o in (ALLOWING, MISSING, BLOCKING)]
            + [(second, o) for o in (ALLOWING, MISSING, BLOCKING)]
        )

    def test_a_changed_verdict_inside_one_job_is_a_new_row(self):
        rows: list = []
        recorder = PolicyVerdictRecorder(lambda job, origin, v: rows.append((job, origin, v)))
        now = datetime.now(UTC)
        recorder.observe(1, f"{ALLOWING}/a", PolicyVerdict(PolicyDecision.ALLOWED, "ok", now))
        recorder.observe(1, f"{ALLOWING}/b", PolicyVerdict(PolicyDecision.ALLOWED, "ok", now))
        recorder.observe(1, f"{ALLOWING}/c", PolicyVerdict(PolicyDecision.BLOCKED, "no", now))
        assert [v.decision for _, _, v in rows] == [
            PolicyDecision.ALLOWED,
            PolicyDecision.BLOCKED,
        ]


class TestEnforcementUnchanged:
    def test_blocked_host_is_recorded_and_still_not_fetched(
        self, tracker, settings, robots_calls
    ):
        rows: list = []
        adapter = StubAdapter(_refs())
        job_id = tracker.create(JobKind.INGEST, {})
        outcome = _run(
            _build(adapter, tracker, settings, AccessPolicyChecker(settings), rows), job_id
        )

        assert (BLOCKING, PolicyDecision.BLOCKED) in {
            (origin, v.decision) for _, origin, v in rows
        }
        fetched_hosts = {
            f"https://{urlparse(ref.url).netloc}"
            for ref in _refs()
            if ref.ref_key in adapter.fetch_calls
        }
        assert BLOCKING not in fetched_hosts
        assert outcome.failures_by_kind == {FailureKind.POLICY_BLOCKED.value: 2}
        assert outcome.succeeded == 5


class _FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        pass


class TestRepositoryRows:
    def test_document_origin_row_is_scoped_and_leaves_source_state(self):
        session = _FakeSession()
        source = SimpleNamespace(
            id=4, policy_status="unknown", policy_reason="robots.txt not published",
            policy_checked_at=None,
        )
        now = datetime.now(UTC)
        SourceRepo(session).record_document_origin_policy(
            source, 12, BLOCKING, PolicyDecision.BLOCKED, "disallowed", now
        )

        (row,) = session.added
        assert row.scope == PolicyCheckScope.DOCUMENT_ORIGIN.value
        assert (row.job_id, row.url, row.decision) == (12, BLOCKING, "blocked")
        # One vendor host refusing is not the source being uncollectable.
        assert source.policy_status == "unknown"

    def test_base_url_row_says_it_is_the_base_url_check(self):
        session = _FakeSession()
        source = SimpleNamespace(
            id=4, policy_status="unknown", policy_reason=None, policy_checked_at=None
        )
        SourceRepo(session).record_policy(
            source, "https://msds.kosha.or.kr", PolicyDecision.UNKNOWN,
            "robots.txt not published", datetime.now(UTC),
        )
        (row,) = session.added
        assert row.scope == PolicyCheckScope.SOURCE_BASE_URL.value
        assert row.job_id is None
