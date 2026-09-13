"""Record the policy verdicts a job actually enforced (D8, CON-3).

`IngestionOrchestrator._handle_one` checks every document URL and the checker
judges per origin, so enforcement was always right. What was missing is the
record: the only `policy_check` row was the source-level check of `base_url`,
and the per-document verdicts reached the log and nothing else. For `msds_pdf`
that row said "unknown" about msds.kosha.or.kr while every document came from a
different host, and reading that row as the policy of the source led to the
wrong conclusion on 2026-09-07.

This class decides *when* a verdict is written; the orchestrator stays free of
persistence and the service supplies the sink (DD-20).
"""

from __future__ import annotations

from collections.abc import Callable

from app.ingestion.policy import PolicyVerdict, origin_of

# (job_id, origin, verdict) - the sink writes one `policy_check` row per call.
VerdictSink = Callable[[int, str, PolicyVerdict], None]


class PolicyVerdictRecorder:
    def __init__(self, sink: VerdictSink) -> None:
        self._sink = sink
        self._written: set[tuple[int, str, str, str]] = set()

    def observe(self, job_id: int, url: str, verdict: PolicyVerdict) -> None:
        origin = origin_of(url)
        # Boundary: one row per (job, origin, verdict).
        #
        # - Per origin, not per URL: the checker judges and caches per origin,
        #   so twenty-seven documents on one host are one verdict, and a row per
        #   URL would repeat it twenty-seven times.
        # - The job is in the key so a later job writes its own rows even when
        #   the verdict is identical. The question the table answers is "what
        #   was enforced in this run", and a row borrowed from an earlier run
        #   cannot answer it.
        # - The verdict (decision + reason) is in the key, not `checked_at`, so
        #   a cached verdict and a re-evaluation that came back the same are the
        #   same fact and are not written twice. A re-evaluation that came back
        #   *different* inside one job (the cache TTL expired and robots.txt
        #   changed) is a second fact and does get its own row.
        # - The set lives on this instance, which the service builds per
        #   `execute`. A job resumed in a new worker process checks again and
        #   records again; that is a new check, not a duplicate.
        key = (job_id, origin, verdict.decision.value, verdict.reason)
        if key in self._written:
            return
        self._written.add(key)
        self._sink(job_id, origin, verdict)
