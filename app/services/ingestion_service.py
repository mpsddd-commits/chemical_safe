"""S1 IngestionService - workflow W1.

`start` does three things and returns: check the policy, create the job, hand it
to the queue (BR-47). It deliberately does no collecting, because a run over a
thousand documents cannot live inside an HTTP request.

`execute` is the worker half. Splitting them this way is also what lets the CLI
run the exact same code path without a queue.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters.sources import build_adapter, load_source_specs
from app.adapters.sources.api_sources import SubstanceApiAdapter
from app.core.config import Settings, get_settings
from app.core.errors import (
    ApiKeyMissingError,
    ConfigurationError,
    OriginalsNotWritableError,
    PolicyBlockedError,
)
from app.core.logging import get_logger
from app.core.types import DocType, JobKind, JobProgress, JobStatus, PolicyDecision, SourceRef
from app.db.engine import session_scope
from app.db.repositories.catalog import SourceRepo
from app.db.repositories.documents import DocumentRepo
from app.db.repositories.jobs import JobRepo
from app.ingestion import substance_selection
from app.ingestion.change_detector import ChangeDetector
from app.ingestion.orchestrator import IngestionOrchestrator
from app.ingestion.originals import ensure_originals_writable
from app.ingestion.policy import AccessPolicyChecker
from app.jobs.tracker import JobTracker
from app.services.indexing_service import IndexingService

log = get_logger(__name__)


@dataclass
class StartResult:
    job_id: int | None
    accepted: bool
    reason: str | None = None


class IngestionService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._s = session
        self._settings = settings or get_settings()
        self._sources = SourceRepo(session)
        self._documents = DocumentRepo(session)
        self._jobs = JobRepo(session)
        # Progress must be visible while the run is in flight (FR-6).
        self._tracker = JobTracker(self._jobs, commit=session.commit)
        self._policy = AccessPolicyChecker(self._settings)
        self._changes = ChangeDetector()

    # ---- catalogue ----
    def sync_source_catalog(self) -> int:
        """Reconcile `config/sources.yaml` into the `source` table."""
        specs = load_source_specs()
        for spec in specs:
            self._sources.upsert(
                source_id=spec["source_id"],
                name=spec["name"],
                kind=spec["kind"],
                base_url=spec["base_url"],
                doc_type=spec["doc_type"],
                requires_api_key=bool(spec.get("requires_api_key")),
                api_key_env=spec.get("api_key_env"),
            )
        return len(specs)

    def list_sources(self) -> list[dict]:
        rows = []
        for source in self._sources.list_all():
            configured = True
            if source.requires_api_key and source.api_key_env:
                configured = bool(self._settings.api_key_for(source.api_key_env))
            rows.append(
                {
                    "source_id": source.source_id,
                    "name": source.name,
                    "kind": source.kind,
                    "doc_type": source.doc_type,
                    "policy_status": source.policy_status,
                    "policy_reason": source.policy_reason,
                    "last_collected_at": source.last_collected_at,
                    "requires_api_key": source.requires_api_key,
                    "api_key_env": source.api_key_env,
                    # BR-02 - the UI disables the button rather than letting the
                    # run fail deep inside the worker.
                    "api_key_configured": configured,
                    "enabled": source.enabled,
                }
            )
        return rows

    # ---- W1 start (synchronous part) ----
    def start(self, source_id: str, since: datetime | None = None) -> StartResult:
        source = self._sources.get(source_id)
        if source is None or not source.enabled:
            return StartResult(None, False, f"unknown or disabled source: {source_id}")

        # BR-02 - fail before creating a job that cannot possibly succeed.
        if source.requires_api_key and source.api_key_env:
            if not self._settings.api_key_for(source.api_key_env):
                return StartResult(
                    None,
                    False,
                    f"인증키 미설정: {source.api_key_env} 환경변수를 설정하세요",
                )

        # BR-03 - a blocked source does not get a job at all.
        verdict = self._policy.check(source.base_url)
        self._sources.record_policy(
            source, source.base_url, verdict.decision, verdict.reason, verdict.checked_at
        )
        if verdict.decision is PolicyDecision.BLOCKED:
            return StartResult(None, False, f"정책상 수집 불가: {verdict.reason}")

        job_id = self._tracker.create(
            JobKind.INGEST,
            {"source_id": source_id, "since": since.isoformat() if since else None},
        )
        return StartResult(job_id, True)

    async def enqueue(self, job_id: int, source_id: str, since: datetime | None) -> None:
        # Imported here: `arq` is a worker-side dependency, and importing it at
        # module level kept the host test run from loading this service at all.
        from app.jobs.queue import TaskQueue

        queue = TaskQueue(self._settings)
        try:
            await queue.enqueue(
                "run_ingest",
                job_id=job_id,
                source_id=source_id,
                since=since.isoformat() if since else None,
            )
        finally:
            await queue.close()

    def start_and_enqueue(self, source_id: str, since: datetime | None = None) -> StartResult:
        result = self.start(source_id, since)
        if result.accepted and result.job_id is not None:
            asyncio.run(self.enqueue(result.job_id, source_id, since))
        return result

    # ---- W1 execute (worker part) ----
    def execute(self, job_id: int, source_id: str, since: str | None = None) -> dict:
        # D9 - before anything is fetched. Every ingestion path reaches here:
        # the CLI calls it inline, and the admin button and the API enqueue
        # `run_ingest`, which calls it in the worker. The check is not in
        # `start` on purpose: the web app starts jobs from a container whose
        # originals mount is read-only, and that is correct as long as the
        # worker does the collecting.
        try:
            ensure_originals_writable(self._settings.originals_dir)
        except OriginalsNotWritableError as exc:
            log.error(
                "ingest_refused_originals_not_writable",
                extra={"job_id": job_id, "source_id": source_id, "error": str(exc)},
            )
            self._tracker.mark_failed(
                job_id, f"{source_id}:__originals__", exc.kind, str(exc)
            )
            status = self._tracker.finalize(job_id)
            return {"status": status.value, "error": str(exc), "refused": True}

        spec = next(
            (s for s in load_source_specs() if s["source_id"] == source_id), None
        )
        if spec is None:
            raise ConfigurationError(f"source {source_id} is not declared in config")

        source = self._sources.get(source_id)
        if source is None:
            raise ConfigurationError(f"source {source_id} is not in the catalogue")

        adapter = build_adapter(spec, self._settings)
        if isinstance(adapter, SubstanceApiAdapter):
            # BR-08. The terms are read here rather than in the adapter because
            # they come out of the database, and a source adapter that queries
            # the database is no longer a source adapter. Collect the accident
            # source first and the MSDS documents after that, and each later
            # substance collection starts from a better list than the one
            # before it.
            adapter.priority_terms = tuple(
                substance_selection.candidate_terms(
                    self._documents.substance_mentions(exclude_source_pk=source.id)
                )
            )
        doc_type = DocType(spec["doc_type"])

        self._tracker.start(job_id)

        since_dt = datetime.fromisoformat(since) if since else source.last_collected_at
        orchestrator = IngestionOrchestrator(
            adapter, self._tracker, self._policy, self._changes, settings=self._settings
        )

        def known_document_for(ref: SourceRef):
            return self._documents.find_by_external(source.id, ref.external_id)

        source_pk = source.id

        def process(raw) -> int:
            """DD-24 / BR-53 - one document, one transaction.

            Running the whole job in the coordinator's session would hold locks
            for hours and discard every success on the first failure, which is
            the opposite of what FR-8 asks for.
            """
            with session_scope() as doc_session:
                return (
                    IndexingService(doc_session, self._settings)
                    .process(raw, doc_type, source_pk=source_pk)
                    .document_id
                )

        try:
            outcome = orchestrator.run(job_id, since_dt, known_document_for, process)
        except ApiKeyMissingError as exc:
            self._tracker.mark_failed(
                job_id, f"{source_id}:__list__", exc.kind, str(exc)
            )
            status = self._tracker.finalize(job_id)
            return {"status": status.value, "error": str(exc)}
        except PolicyBlockedError as exc:
            self._tracker.mark_failed(
                job_id, f"{source_id}:__list__", exc.kind, str(exc)
            )
            status = self._tracker.finalize(job_id)
            return {"status": status.value, "error": str(exc)}

        status = self._tracker.finalize(job_id)
        # BR-13 - a fully failed run leaves the watermark alone so the next run
        # covers the same window.
        if status in (JobStatus.SUCCEEDED, JobStatus.PARTIAL):
            self._sources.mark_collected(source, datetime.now(UTC))

        return {"status": status.value, **outcome.as_dict()}

    # ---- queries ----
    def job_status(self, job_id: int) -> JobProgress:
        return self._tracker.progress(job_id)

    def list_jobs(
        self, statuses: list[str] | None = None, kind: str | None = None, limit: int = 25
    ) -> list:
        return self._jobs.list_jobs(statuses=statuses, kind=kind, limit=limit)

    def job_items(self, job_id: int, status: str | None = None, limit: int = 200) -> list:
        return self._jobs.list_items(job_id, status=status, limit=limit)
