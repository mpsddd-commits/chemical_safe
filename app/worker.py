"""C59 Worker entry point.

The heartbeat exists so `/healthz` can distinguish "no jobs running" from "the
worker died" (BR-52). Without it the web process would report healthy while
nothing is being processed.

It runs as a plain asyncio task, not as an arq cron job. As a cron job it was
itself a queued job, and `max_jobs = 1` meant it could not run while an
ingestion job held the only slot: measured during a real run, the heartbeat went
stale after 134 seconds against a 120 second threshold, so `/healthz` reported
the worker down while it was indexing normally - the exact false signal BR-52
exists to prevent, inverted. A liveness signal must not depend on the queue it
is reporting on.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import socket

from app.core.config import get_settings
from app.core.logging import configure, get_logger
from app.db.engine import init_engine, session_scope
from app.db.repositories.jobs import WorkerHeartbeatRepo
from app.jobs.queue import redis_settings
from app.jobs.tasks import run_index_upload, run_ingest, run_reindex

log = get_logger(__name__)

WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"


def _beat() -> None:
    """One heartbeat write. Synchronous, so it is called off the event loop."""
    with session_scope() as session:
        WorkerHeartbeatRepo(session).beat(WORKER_ID)


async def heartbeat() -> None:
    """BR-52 - a single beat, safe to call at any time."""
    try:
        await asyncio.to_thread(_beat)
    except Exception as exc:  # noqa: BLE001 - a missed beat must not kill the worker
        log.warning("heartbeat_failed", extra={"error": str(exc)})


async def _heartbeat_loop(interval: int) -> None:
    while True:
        await heartbeat()
        await asyncio.sleep(interval)


async def startup(ctx: dict) -> None:
    settings = get_settings()
    configure(settings.log_level, settings.log_dir)
    init_engine(settings)
    # Beat once before accepting work so the container probe passes immediately
    # rather than after a full interval.
    await heartbeat()
    ctx["heartbeat_task"] = asyncio.create_task(
        _heartbeat_loop(settings.worker_heartbeat_interval)
    )
    log.info("worker_started", extra={"worker_id": WORKER_ID})


async def shutdown(ctx: dict) -> None:
    task = ctx.pop("heartbeat_task", None)
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    log.info("worker_stopped", extra={"worker_id": WORKER_ID})


class WorkerSettings:
    functions = [run_ingest, run_reindex, run_index_upload]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings()
    # No `cron_jobs`: the heartbeat is a plain asyncio task now. As a cron job it
    # queued behind the running ingestion job and could never tick (max_jobs=1).
    max_jobs = 1
    job_timeout = 60 * 60 * 8  # a full initial index can take hours (NFR-4)
    keep_result = 3600
