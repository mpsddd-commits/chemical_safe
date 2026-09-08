"""HTML pages for u2 - P5, and the no-JavaScript answer path.

u1 established that every screen works without JavaScript and that `app.js` only
adds progressive enhancement (DD-17). Streaming cannot honour that on its own,
so `POST /query` renders the same answer server-side, synchronously.

It is not a lesser path. It runs the identical `QueryService.answer`, so the id
whitelist (SP-8), grounding verification (BR-85~87) and the frozen citations
(BR-92) are all the same. The only thing it gives up is watching the text
arrive.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.ownership import scope_for
from app.auth.types import AuthenticatedUser
from app.core.config import get_settings
from app.core.errors import ConfigurationError
from app.core.logging import get_logger
from app.core.types import AnswerOutcome
from app.db.engine import observability_scope
from app.rag import refusal as refusal_rules
from app.web.deps import admin_flag, current_user, get_session

log = get_logger(__name__)
router = APIRouter(tags=["pages"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

REFUSAL_TEXT = {
    "no_candidates": "관련 문서를 찾지 못했습니다.",
    "below_threshold": "검색된 문서의 관련도가 기준에 미치지 못했습니다.",
    "all_sentences_unsupported": "생성된 문장이 근거로 뒷받침되지 않았습니다.",
    # C15. Not "근거가 부족합니다": nothing was judged, so nothing was found
    # lacking. The question was fine and the evidence was fine - the checking
    # step could not run, and the user must not read this as their mistake.
    "verification_unavailable": (
        "지금은 근거 검증을 할 수 없어 답변을 보류했습니다. "
        "질문이나 자료의 문제가 아니라 검증 단계가 실행되지 못한 것이며, "
        "잠시 후 다시 시도해 주시면 답변을 드릴 수 있습니다."
    ),
    "provider_refusal": "모델이 이 질문에 대한 답변을 거부했습니다.",
    # BR-73a. Worded as a request, not a dead end: the evidence found is about
    # specific substances and we could not tell which one was asked about, so
    # naming it is the one thing that turns this into an answer.
    "unknown_subject": (
        "어떤 물질에 대한 질문인지 확인하지 못했습니다. "
        "물질명이나 CAS 번호를 함께 적어 주시면 해당 물질의 자료로 답변합니다. "
        "아래는 검색된 문서입니다."
    ),
}

# The headline is what the user reads first, and until 2026-09-08 it was fixed
# text in `query.html` saying every refusal was a missing-evidence refusal. C15
# added one that is not: `verification_unavailable` means nothing was judged, so
# the screen announced "근거를 찾지 못했습니다" and then the reason line under it
# said the opposite. The headline wins that contest, and the user goes off to
# rewrite a question that was never the problem - in a safety domain that is
# time spent editing instead of reading an MSDS, for an answer that was one
# retry away. So the headline is chosen by reason, like the reason text is.
#
# (Backlog D10 - naming 카드뮴 and being told we could not tell which substance
# was asked about - is this same failure from a different cause: UNKNOWN_SUBJECT
# covers two situations. Tracked separately; not fixed here.)
DEFAULT_REFUSAL_HEADLINE = "ⓘ 이 질문에 답할 근거를 찾지 못했습니다."

# Overrides only. A reason that is absent keeps the default, which is the right
# sentence for every refusal that really is "we looked and found nothing".
REFUSAL_HEADLINE = {
    "verification_unavailable": "ⓘ 답변을 보류했습니다.",
}


def _context(request: Request, **extra) -> dict:
    # `is_admin` defaults to False rather than being required: a caller that
    # forgets it hides the admin links, which is the safe direction to fail in.
    return {
        "active": "query",
        "query_max_chars": get_settings().query_max_chars,
        "is_admin": False,
        # Present on every render so the template never has to hold a copy of
        # the sentence; a refusal overrides it below.
        "refusal_headline": DEFAULT_REFUSAL_HEADLINE,
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
def query_page(
    request: Request,
    user: AuthenticatedUser | None = Depends(current_user),
    is_admin: bool = Depends(admin_flag),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "query.html", _context(request, user=user, is_admin=is_admin)
    )


@router.post("/query", response_class=HTMLResponse)
def query_submit(
    request: Request,
    question: str = Form(...),
    session: Session = Depends(get_session),
    user: AuthenticatedUser | None = Depends(current_user),
    is_admin: bool = Depends(admin_flag),
) -> HTMLResponse:
    from app.adapters.embedding_local import shared_adapter
    from app.adapters.llm_factory import build_entity_llm, build_llm, build_verify_llm
    from app.adapters.tracing import TracedEmbedding
    from app.services.query_service import QueryService

    settings = get_settings()
    question = question.strip()[: settings.query_max_chars]  # SP-7

    try:
        # Observability on its own transaction, so a failure still records that
        # the query was attempted (BR-78, BR-95).
        with observability_scope() as obs:
            result = QueryService(
                session,
                llm=build_llm(),
                entity_llm=build_entity_llm(),
            verify_llm=build_verify_llm(),
                embedder=TracedEmbedding(shared_adapter()),
                obs_session=obs,
            ).answer(question, scope_for(user))
    except ConfigurationError as exc:
        # BR-02 - the app is running; querying is not configured.
        return templates.TemplateResponse(
            request,
            "query.html",
            _context(request, question=question, error=str(exc), user=user, is_admin=is_admin),
            status_code=503,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("query_failed")
        return templates.TemplateResponse(
            request,
            "query.html",
            _context(request, question=question, error=str(exc), user=user, is_admin=is_admin),
            status_code=500,
        )

    refused = result.outcome in {
        AnswerOutcome.REFUSED_LOW_RELEVANCE,
        AnswerOutcome.REFUSED_UNSUPPORTED,
    }
    return templates.TemplateResponse(
        request,
        "query.html",
        _context(
            request,
            question=question,
            result=result,
            refused=refused,
            refusal_text=REFUSAL_TEXT.get(
                result.refusal_reason.value if result.refusal_reason else "",
                "답변할 근거가 부족합니다.",
            ),
            refusal_headline=REFUSAL_HEADLINE.get(
                result.refusal_reason.value if result.refusal_reason else "",
                DEFAULT_REFUSAL_HEADLINE,
            ),
            # BR-75 - a refusal always offers somewhere to go.
            links=result.links or refusal_rules.source_links([]),
            user=user,
            is_admin=is_admin,
        ),
    )
