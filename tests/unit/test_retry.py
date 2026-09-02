"""RetryPolicy — BR-41, BR-42, BR-43.

Includes property-based tests (NFR-27). `RetryPolicy` is a pure component, so
Hypothesis can explore attempt counts and schedules without any test doubles.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.errors import (
    ExtractionError,
    FailureKind,
    PolicyBlockedError,
    SourceNotFoundError,
    SourceUnavailableError,
)
from app.ingestion.retry import RetryPolicy


@pytest.fixture
def policy() -> RetryPolicy:
    return RetryPolicy(max_attempts=3, backoff_schedule=(1.0, 4.0, 16.0), total_wait_cap=60.0)


class TestClassification:
    def test_network_failure_is_transient(self, policy):
        assert policy.classify(SourceUnavailableError("timeout")) is FailureKind.TRANSIENT

    def test_client_error_is_permanent(self, policy):
        assert policy.classify(SourceNotFoundError("404")) is FailureKind.PERMANENT

    def test_extraction_failure_is_permanent(self, policy):
        assert policy.classify(ExtractionError("scanned pdf")) is FailureKind.PERMANENT

    def test_policy_block_is_its_own_kind(self, policy):
        """BR-43 — must not collapse into PERMANENT.

        The two differ on re-run: a permanent failure is retried on the next run
        because the source may have been fixed (BR-45); a policy block is not.
        """
        assert policy.classify(PolicyBlockedError("robots")) is FailureKind.POLICY_BLOCKED

    def test_unknown_exception_defaults_to_permanent(self, policy):
        assert policy.classify(ValueError("bad data")) is FailureKind.PERMANENT

    def test_os_error_is_transient(self, policy):
        assert policy.classify(ConnectionError("reset")) is FailureKind.TRANSIENT


class TestShouldRetry:
    def test_transient_retried_until_max(self, policy):
        error = SourceUnavailableError("503")
        assert policy.should_retry(1, error) is True
        assert policy.should_retry(2, error) is True
        assert policy.should_retry(3, error) is False

    def test_permanent_never_retried(self, policy):
        assert policy.should_retry(1, SourceNotFoundError("404")) is False

    def test_policy_blocked_never_retried(self, policy):
        assert policy.should_retry(1, PolicyBlockedError("disallowed")) is False


class TestBackoff:
    def test_schedule_is_followed(self, policy):
        assert policy.next_delay(1) == 1.0
        assert policy.next_delay(2) == 4.0

    def test_delay_clamped_by_total_cap(self):
        tight = RetryPolicy(max_attempts=5, backoff_schedule=(30.0, 30.0, 30.0),
                            total_wait_cap=45.0)
        assert tight.next_delay(1) == 30.0
        # 30s already spent, so the second wait cannot exceed the remaining 15s.
        assert tight.next_delay(2) == 15.0
        assert tight.next_delay(3) == 0.0


class TestProperties:
    """NFR-27 — property-based coverage of the pure component."""

    @given(attempt=st.integers(min_value=-5, max_value=50))
    def test_delay_is_never_negative(self, attempt):
        policy = RetryPolicy()
        assert policy.next_delay(attempt) >= 0.0

    @given(attempt=st.integers(min_value=1, max_value=50))
    def test_delay_never_exceeds_cap(self, attempt):
        policy = RetryPolicy(backoff_schedule=(5.0, 25.0, 125.0), total_wait_cap=60.0)
        assert policy.next_delay(attempt) <= 60.0

    @given(attempts=st.integers(min_value=1, max_value=20))
    def test_total_wait_is_bounded(self, attempts):
        policy = RetryPolicy(backoff_schedule=(10.0, 10.0, 10.0), total_wait_cap=25.0)
        assert policy.total_wait_for(attempts) <= 25.0

    @given(
        attempt=st.integers(min_value=1, max_value=10),
        max_attempts=st.integers(min_value=1, max_value=10),
    )
    def test_retry_stops_at_max_regardless_of_error(self, attempt, max_attempts):
        policy = RetryPolicy(max_attempts=max_attempts)
        if attempt >= max_attempts:
            assert policy.should_retry(attempt, SourceUnavailableError("x")) is False

    @given(st.sampled_from([PolicyBlockedError("p"), SourceNotFoundError("n"),
                            ExtractionError("e")]))
    def test_non_transient_is_never_retried_at_any_attempt(self, error):
        policy = RetryPolicy(max_attempts=99)
        assert all(policy.should_retry(a, error) is False for a in range(1, 20))
