"""C17 IngestionOrchestrator - workflow W1 step 6 onwards.

One failing document never stops the run (BR-40). That is the whole reason the
job/item split exists: a run over a thousand MSDS files will hit malformed PDFs,
and the useful outcome is 980 indexed documents plus 20 diagnosable failures,
not an abort.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime

from app.core.config import Settings, get_settings
from app.core.errors import FailureKind, PolicyBlockedError
from app.core.logging import get_logger
from app.core.types import PipelineStage, RawDocument, SourceRef
from app.ingestion.change_detector import ChangeDetector
from app.ingestion.policy import AccessPolicyChecker
from app.ingestion.retry import RetryPolicy
from app.jobs.tracker import JobTracker
from app.ports.source import SourceAdapter

log = get_logger(__name__)


@dataclass
class IngestionOutcome:
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0
    failures_by_kind: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "succeeded": self.succeeded,
            "skipped": self.skipped,
            "failed": self.failed,
            "failures_by_kind": self.failures_by_kind,
        }


class IngestionOrchestrator:
    def __init__(
        self,
        adapter: SourceAdapter,
        tracker: JobTracker,
        policy: AccessPolicyChecker,
        change_detector: ChangeDetector,
        *,
        settings: Settings | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._adapter = adapter
        self._tracker = tracker
        self._policy = policy
        self._changes = change_detector
        self._settings = settings or get_settings()
        self._retry = RetryPolicy.from_settings(self._settings)
        self._sleep = sleep

    def run(
        self,
        job_id: int,
        since: datetime | None,
        known_document_for: Callable[[SourceRef], object | None],
        process: Callable[[RawDocument], int],
    ) -> IngestionOutcome:
        """`process` performs W2+W3 for one document and returns its document id.

        It is injected rather than imported so that the orchestrator stays free
        of persistence concerns and can be tested with a stub (DD-20).
        """
        outcome = IngestionOutcome()

        refs = list(self._list_targets(since))
        self._tracker.add_items(job_id, [r.ref_key for r in refs])
        blocked = self._tracker.blocked_ref_keys(job_id)

        for ref in refs:
            if ref.ref_key in blocked:
                # BR-43 - stays skipped until the policy verdict itself changes.
                continue
            self._handle_one(job_id, ref, known_document_for, process, outcome)

        return outcome

    # ---- internals ----
    def _list_targets(self, since: datetime | None) -> Iterator[SourceRef]:
        try:
            yield from self._adapter.list_targets(since)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a job failure
            log.error(
                "list_targets_failed",
                exc_info=exc,
                extra={"source_id": self._adapter.source_id()},
            )
            raise

    def _handle_one(
        self,
        job_id: int,
        ref: SourceRef,
        known_document_for: Callable[[SourceRef], object | None],
        process: Callable[[RawDocument], int],
        outcome: IngestionOutcome,
    ) -> None:
        # BR-03 - every fetch is preceded by a policy verdict, per URL.
        verdict = self._policy.check(ref.url)
        if verdict.decision.value == "blocked":
            self._fail(
                job_id, ref, PolicyBlockedError(verdict.reason), outcome,
                stage=PipelineStage.FETCH, attempts=1,
            )
            return

        # BR-09 - skip unchanged documents before spending a request.
        known = known_document_for(ref)
        if known is not None and not self._changes.has_changed(ref, known):  # type: ignore[arg-type]
            self._tracker.mark_skipped(job_id, ref.ref_key)
            outcome.skipped += 1
            return

        attempt = 0
        while True:
            attempt += 1
            try:
                raw = self._adapter.fetch(ref)
                document_id = process(raw)
            except Exception as exc:  # noqa: BLE001 - classified below
                if self._retry.should_retry(attempt, exc):
                    delay = self._retry.next_delay(attempt)
                    log.info(
                        "ingest_retry",
                        extra={
                            "ref_key": ref.ref_key,
                            "attempt": attempt,
                            "delay_s": delay,
                        },
                    )
                    self._sleep(delay)
                    continue
                self._fail(job_id, ref, exc, outcome, stage=PipelineStage.FETCH,
                           attempts=attempt)
                return
            else:
                self._tracker.mark_succeeded(job_id, ref.ref_key, document_id, attempts=attempt)
                outcome.succeeded += 1
                return

    def _fail(
        self,
        job_id: int,
        ref: SourceRef,
        error: BaseException,
        outcome: IngestionOutcome,
        *,
        stage: PipelineStage,
        attempts: int,
    ) -> None:
        kind: FailureKind = self._retry.classify(error)
        self._tracker.mark_failed(
            job_id, ref.ref_key, kind, str(error), last_stage=stage, attempts=attempts
        )
        outcome.failed += 1
        outcome.failures_by_kind[kind.value] = outcome.failures_by_kind.get(kind.value, 0) + 1
