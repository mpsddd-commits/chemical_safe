"""Query routes - P5 and the SSE contract (FR-14, FR-19, FR-44).

`final` and `refused` are mutually exclusive and exactly one of them is always
sent. A client must never infer success from the stream simply ending: a dropped
connection and a completed answer look identical otherwise, and here that
difference is "the user believes an unverified answer".

Generation runs in a worker thread so its blocking HTTP calls do not stall the
event loop; events cross back on a queue.
"""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConfigurationError, QuotaExhaustedError
from app.core.logging import get_logger
from app.db.engine import observability_scope, session_scope
from app.db.repositories.queries import QueryRepo
from app.rag.citations import citations_for_answer

log = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["query"])

_SENTINEL = object()


def get_session() -> Session:
    with session_scope() as session:
        yield session


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def _validate(cls, value: str) -> str:
        """SP-9 / SP-7 - the question is untrusted input, validated server-side."""
        cleaned = "".join(ch for ch in value if ch.isprintable() or ch in "\n\t").strip()
        if not cleaned:
            raise ValueError("question must not be empty")
        limit = get_settings().query_max_chars
        if len(cleaned) > limit:
            raise ValueError(f"question must be at most {limit} characters")
        return cleaned


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _build_service(session: Session, obs_session: Session):
    from app.adapters.embedding_local import shared_adapter
    from app.adapters.llm_factory import build_entity_llm, build_llm, build_verify_llm
    from app.adapters.tracing import TracedEmbedding
    from app.services.query_service import QueryService

    return QueryService(
        session,
        llm=build_llm(),
        entity_llm=build_entity_llm(),
        verify_llm=build_verify_llm(),
        embedder=TracedEmbedding(shared_adapter()),
        obs_session=obs_session,
    )


@router.post("/query")
def query(
    request: QueryRequest,
    http_request: Request,
) -> StreamingResponse:
    """Streaming answers, now owner-aware.

    This endpoint hard-coded the public scope until u5. Left that way it would
    have been the one path where a signed-in user's own uploads never appeared -
    the SSR form would find them and the streaming one would not, for the same
    question.
    """
    from app.auth.ownership import scope_for
    from app.web.deps import current_user

    scope = scope_for(current_user(http_request))
    events: queue.Queue = queue.Queue()

    def emit(event: str, data: dict) -> None:
        events.put((event, data))

    def run() -> None:
        try:
            # Two sessions, and its own of each: this runs on another thread and
            # a Session is not safe to share across threads.
            #
            # `observability_scope` is outside `session_scope` so it outlives the
            # rollback. A failed query still leaves its `query_log` row and its
            # `llm_call` rows behind - the point of the split.
            with observability_scope() as obs, session_scope() as session:
                _build_service(session, obs).answer(
                    request.question, scope, emit
                )
        except ConfigurationError as exc:
            # BR-02 - no API key. The app is up; querying is not configured.
            emit("error", {"kind": "configuration", "message": str(exc)})
        except QuotaExhaustedError as exc:
            # Its own kind: "wait" and "broken" must not read the same. On the
            # free tier this is the ordinary end of a development session.
            emit(
                "error",
                {
                    "kind": "quota",
                    "message": exc.message,
                    "retry_after_seconds": exc.retry_after_seconds,
                },
            )
        except Exception as exc:  # noqa: BLE001 - the stream must terminate cleanly
            log.exception("query_failed")
            emit("error", {"kind": "transient", "message": str(exc)})
        finally:
            events.put(_SENTINEL)

    threading.Thread(target=run, daemon=True).start()

    def stream() -> Iterator[str]:
        while True:
            item = events.get()
            if item is _SENTINEL:
                return
            event, data = item
            yield _sse(event, data)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/query/{query_id}", include_in_schema=True)
def get_query(query_id: int, session: Session = Depends(get_session)) -> dict:
    repo = QueryRepo(session)
    row = repo.get(query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="query not found")
    sentences = repo.sentences_for(query_id)
    return {
        "query_id": row.id,
        "question": row.question,
        "outcome": row.outcome,
        "refusal_reason": row.refusal_reason,
        "mode": row.mode,
        "retrieval_ms": row.retrieval_ms,
        "total_ms": row.total_ms,
        "sentences": [
            {
                "ordinal": s.ordinal,
                "text": s.text,
                "support": s.support,
                "removed": s.removed,
            }
            for s in sentences
        ],
        # BR-92a - read from the snapshot, never from `chunk`.
        "citations": citations_for_answer(session, query_id),
    }


@router.get("/citations/{citation_id}/snippet")
def citation_snippet(
    citation_id: int, session: Session = Depends(get_session)
) -> dict:
    """BR-92a - keyed by citation, not by chunk.

    Keying on `chunk_id` was the earlier design and it was wrong: re-indexing
    reuses chunk ids, so a past citation could resolve to a different document's
    text under the original label.
    """
    snapshot = QueryRepo(session).snapshot_for_citation(citation_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="citation not found")
    from app.rag.citations import display_label

    return {
        "citation_id": snapshot.citation_id,
        "document_id": snapshot.document_id,
        "title": snapshot.document_title,
        "label": display_label(snapshot.section_code, snapshot.section_title),
        "snippet": snapshot.snippet,
        "source_url": snapshot.source_url,
    }
