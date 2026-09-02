"""Entry point for the `reranker` container (PP-2, BR-70).

A separate process rather than a module inside `app` because of a measurement:
with the embedding model resident, `app` sits at 1.70GiB of its 2GiB limit, and
a cross-encoder on top of that exceeded it (risk R-4).

Internal only - no host port is published (NFR-18). The model loads lazily, so
the container starts fast and pays for the weights on first use; `start_period`
in the healthcheck covers that first load.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import configure, get_logger

_settings = get_settings()
configure(_settings.log_level, _settings.log_dir)
log = get_logger(__name__)

app = FastAPI(title="safeenv reranker", docs_url=None, redoc_url=None)

DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"

_model: Any = None


def _load() -> Any:
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        log.info("reranker_loading", extra={"model": DEFAULT_MODEL})
        _model = CrossEncoder(DEFAULT_MODEL, cache_folder=str(_settings.model_cache_dir))
        log.info("reranker_loaded", extra={"model": DEFAULT_MODEL})
    return _model


class RerankRequest(BaseModel):
    query: str
    docs: list[str] = Field(default_factory=list)


class RerankResponse(BaseModel):
    # Scores are returned in input order, not sorted. The caller owns the
    # ordering because it also owns the tie-breaking and the fallback path.
    scores: list[float]
    model: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness only - deliberately does not load the model.

    A healthcheck that pulled 2GB of weights would report unhealthy for the
    first two minutes of every restart and would make `app`'s optional
    dependency look like an outage.
    """
    return {"reranker": "ok"}


@app.post("/rerank", response_model=RerankResponse)
def rerank(request: RerankRequest) -> RerankResponse:
    if not request.docs:
        return RerankResponse(scores=[], model=DEFAULT_MODEL)
    model = _load()
    pairs = [(request.query, doc) for doc in request.docs]
    scores = model.predict(pairs)
    return RerankResponse(scores=[float(s) for s in scores], model=DEFAULT_MODEL)
