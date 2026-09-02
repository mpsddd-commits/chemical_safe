"""C29 TaskQueue - enqueue and consume only. It holds no state (DD-13).

Redis persistence is deliberately disabled in compose: losing the queue costs
nothing because every unfinished item is still `pending` in `job_item`, and
re-running the job picks them up (BR-44).
"""

from __future__ import annotations

from typing import Any

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


def redis_settings(settings: Settings | None = None) -> RedisSettings:
    s = settings or get_settings()
    return RedisSettings(host=s.redis_host, port=s.redis_port)


class TaskQueue:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._pool: Any | None = None

    async def _get_pool(self) -> Any:
        if self._pool is None:
            self._pool = await create_pool(redis_settings(self._settings))
        return self._pool

    async def enqueue(self, task_name: str, **payload: Any) -> str | None:
        pool = await self._get_pool()
        job = await pool.enqueue_job(task_name, **payload)
        job_id = getattr(job, "job_id", None)
        log.info("task_enqueued", extra={"task": task_name, "queue_job_id": job_id})
        return job_id

    async def ping(self) -> bool:
        """Health probe for the queue (FR-43)."""
        try:
            pool = await self._get_pool()
            await pool.ping()
            return True
        except Exception as exc:  # noqa: BLE001 - health check must not raise
            log.warning("queue_health_check_failed", extra={"error": str(exc)})
            return False

    async def enqueue_and_close(self, task_name: str, **payload: Any) -> str | None:
        """u5 - the one-shot form a request handler needs.

        A web request has no long-lived queue client to reuse, and leaking the
        connection pool per upload is how a server runs out of sockets.
        """
        try:
            return await self.enqueue(task_name, **payload)
        finally:
            await self.close()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None
