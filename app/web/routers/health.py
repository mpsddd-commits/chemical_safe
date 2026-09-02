"""C58 HealthCheck (FR-43, BR-52).

Reports four components separately. A single boolean would hide the case this
endpoint exists for: the web process answering fine while the worker is dead and
no ingestion is progressing.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.build import build_id
from app.core.config import get_settings
from app.db.engine import check_connection, session_scope
from app.db.repositories.jobs import WorkerHeartbeatRepo
from app.jobs.queue import TaskQueue

router = APIRouter(tags=["health"])


async def collect_health() -> dict:
    settings = get_settings()
    db_ok = check_connection()

    worker_ok = False
    if db_ok:
        try:
            with session_scope() as session:
                worker_ok = WorkerHeartbeatRepo(session).any_alive(
                    settings.worker_stale_threshold
                )
        except Exception:  # noqa: BLE001 - a probe must never raise
            worker_ok = False

    queue = TaskQueue(settings)
    try:
        queue_ok = await queue.ping()
    finally:
        await queue.close()

    return {
        "app": "ok",
        "db": "ok" if db_ok else "down",
        "queue": "ok" if queue_ok else "down",
        "worker": "ok" if worker_ok else "down",
    }


@router.get("/healthz")
async def healthz(response: Response) -> dict:
    report = await collect_health()
    # The status decision reads `report`, never the returned body. `build` is
    # an identity, not a component, and `any(v != "ok")` over the body would
    # have made every probe 503 the moment a non-status field was added -
    # the healthcheck failing *because* it started reporting more (defect 58
    # is about a signal nobody had; this is how you get one that lies).
    if any(v != "ok" for v in report.values()):
        response.status_code = 503
    return {**report, "build": build_id()}
