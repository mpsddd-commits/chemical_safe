"""C16 RetryPolicy - a pure component (BR-41~43).

No I/O, no clock, no state. That is what makes it a property-based test target
(NFR-27) and what lets the orchestrator's retry behaviour be verified without a
network.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import FailureKind, classify


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_schedule: tuple[float, ...] = (1.0, 4.0, 16.0)
    total_wait_cap: float = 60.0

    @classmethod
    def from_settings(cls, settings) -> RetryPolicy:
        return cls(
            max_attempts=settings.max_retry_attempts,
            backoff_schedule=tuple(settings.backoff_schedule),
            total_wait_cap=float(settings.retry_total_wait_cap),
        )

    def classify(self, error: BaseException) -> FailureKind:
        return classify(error)

    def should_retry(self, attempt: int, error: BaseException) -> bool:
        """`attempt` is 1-based: the number of tries already made.

        Only TRANSIENT is retried. PERMANENT is pointless to repeat, and
        POLICY_BLOCKED must never be repeated at all (BR-43).
        """
        if attempt >= self.max_attempts:
            return False
        return self.classify(error) is FailureKind.TRANSIENT

    def next_delay(self, attempt: int) -> float:
        """Delay before try number `attempt + 1`.

        The schedule is clamped by `total_wait_cap` so a long schedule cannot
        make a single item block a job indefinitely.
        """
        if attempt < 1:
            attempt = 1
        index = min(attempt - 1, len(self.backoff_schedule) - 1)
        delay = self.backoff_schedule[index]
        spent = sum(self.backoff_schedule[: attempt - 1])
        remaining = max(0.0, self.total_wait_cap - spent)
        return min(delay, remaining)

    def total_wait_for(self, attempts: int) -> float:
        return min(sum(self.backoff_schedule[: max(0, attempts - 1)]), self.total_wait_cap)
