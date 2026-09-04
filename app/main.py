"""ASGI application assembly (C56 entry point).

Note on binding: `APP_HOST` is 0.0.0.0 inside the container because the
container network has to reach it. External exposure is limited by the
`127.0.0.1:` prefix in docker-compose.yml (NFR-18, ID-12).

That prefix used to be the *only* control over the admin UI. Since B1/B2/B2a it
is not - `/admin`, `/usage` and the `/api` router all require an admin account.
It is still required, and for reasons the authentication does not cover:
`/` and `/substances` are deliberately anonymous (BR-147), there is no server
side token revocation (AP-3), and there is no TLS termination, so removing the
prefix puts session cookies on the wire in clear text.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import configure, get_logger
from app.db.engine import init_engine
from app.web.deps import LoginRequired
from app.web.routers import (
    admin,
    api,
    auth,
    documents,
    health,
    pages,
    query,
    substances,
    usage,
)

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure(settings.log_level, settings.log_dir)
    log = get_logger(__name__)
    init_engine(settings)
    log.info(
        "app_started",
        extra={"host": settings.app_host, "port": settings.app_port,
               "embedding_model": settings.embedding_model_id},
    )
    yield
    log.info("app_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="safeenv",
        description=(
            "화학 안전·규제 근거 기반 질의응답 시스템 — "
            "u1 수집·색인 / u2 질의응답 / u3 물질 카드 / u4 평가 / u5 계정·업로드"
        ),
        version="0.5.0",
        lifespan=lifespan,
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    # BR-137 - the web app authenticates, so it does not start without a
    # signing key. Checked here rather than as a field validator because the CLI
    # and the worker do not authenticate and must not inherit the requirement.
    get_settings().require_jwt_secret()

    @app.exception_handler(LoginRequired)
    def _login_required(request, _exc):
        """u5 - turn the marker exception into an actual redirect.

        `require_user` raises rather than returning None so that a handler
        cannot forget to check. Raising an HTTPException(303) alone produced a
        303 with **no Location header** - the browser stayed put and the page
        looked broken. Found by requesting `/documents` while signed out.
        """
        return RedirectResponse(
            url=f"/login?next={request.url.path}", status_code=status.HTTP_303_SEE_OTHER
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(documents.router)
    app.include_router(api.router)
    app.include_router(query.router)
    app.include_router(usage.router)
    app.include_router(substances.router)
    app.include_router(pages.router)
    app.include_router(admin.router)
    return app


app = create_app()
