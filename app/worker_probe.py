"""Container liveness probe for the worker (BR-52).

The application image declares a single HEALTHCHECK that fetches
`http://127.0.0.1:8000/healthz`. Only the web process serves that, so the worker
container - which runs `arq` - could never pass it and reported `unhealthy` no
matter how well it was working.

Liveness for the worker means "the arq event loop is still ticking", and that is
exactly what the heartbeat cron records. `worker_stale_threshold` (120s by
default) allows two missed beats before the probe fails, so a brief pause does
not flap the container.

Run as `python -m app.worker_probe`; exits 0 when alive, 1 otherwise.
"""

from __future__ import annotations

import sys


def is_alive() -> bool:
    from app.core.config import get_settings
    from app.db.engine import init_engine, session_scope
    from app.db.repositories.jobs import WorkerHeartbeatRepo

    settings = get_settings()
    init_engine(settings)
    with session_scope() as session:
        return WorkerHeartbeatRepo(session).any_alive(settings.worker_stale_threshold)


def main() -> int:
    try:
        return 0 if is_alive() else 1
    except Exception as exc:  # noqa: BLE001 - a probe must never raise
        print(f"worker probe failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
