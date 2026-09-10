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
    # BR-73a / backlog D10. The old wording said two things the system is not
    # entitled to say. "어떤 물질에 대한 질문인지 확인하지 못했습니다" is a claim
    # about the user's text, and it is false whenever they did name one:
    # 카드뮴 is written plainly in the question and still lands here, because
    # `entities._match_synonyms` only puts RESOLVED names into `substance_names`
    # and an unresolved 카드뮴 stays in `raw_terms` - the exact shape of a
    # question that named nothing. And "적어 주시면 답변합니다" is a promise this
    # code cannot keep: adding CAS 7440-43-9 to that same question returns this
    # refusal again, because the corpus holds no 카드뮴 material.
    #
    # UNKNOWN_SUBJECT covers THREE situations the code cannot tell apart:
    # (1) the question names no substance, (2) it names one we do not hold,
    # (3) it names one we DO hold, under a name the synonym table lacks. The
    # reason fires on failure to RESOLVE a name, and failure to resolve is not
    # absence. Measured 2026-09-10, `EntityExtractor.extract` called directly,
    # entity LLM off:
    #
    #     황산은 어떻게 저장하나요    -> names=['황산']            resolved
    #     sulfuric acid 저장법        -> names=['Sulfuric acid']   resolved
    #     H2SO4 저장법                -> names=[]                  UNRESOLVED
    #     유산은 어떻게 저장하나요    -> names=[]                  UNRESOLVED
    #
    # 황산 is held - two MSDS documents plus a substance record - and asking by
    # formula, or by its old name 유산, still lands here. So the first D10
    # wording, "이 질문에 답할 자료는 현재 보유한 자료에 없습니다" (replaced
    # 2026-09-10), was false in exactly those cases: it swapped an overclaim
    # about the user's question for an overclaim about the corpus. Synonyms
    # average two per substance, so case (3) is not a corner case. Do not put
    # "없습니다" back. What the system knows is that it did not FIND material
    # for this question, never that it does not HAVE it - and every sentence
    # here has to be true in all three situations. (Widening the synonym table
    # is a separate backlog item; it would shrink case (3), not make the
    # stronger claim safe.) The next action is the substance list, which is a
    # fact about the corpus rather than a rewrite of the question, and which
    # now also answers "under which name do they file it". The count is
    # deliberately not repeated here - `/substances` owns it.
    #
    # Sentence order is deliberate and unchanged. The headline above already
    # says 근거를 찾지 못했습니다, so leading the reason with the same news adds
    # nothing; what it must add first is the warning about the documents
    # rendered directly below it, because a reader who takes another
    # substance's MSDS for the answer is the one failure here that carries
    # real safety cost. Not-found follows as the reason, the list last as the
    # next action.
    "unknown_subject": (
        "아래 문서는 특정 물질의 자료이며 이 질문에 대한 답이 아닙니다. "
        "이 질문에 맞는 자료를 찾지 못했으며, 같은 물질이라도 이름이나 표기가 "
        "자료와 다르면 찾지 못할 수 있습니다. "
        "어떤 물질을 다루고 있는지는 '물질' 메뉴의 목록에서 확인하실 수 있습니다."
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
# was asked about - was this same failure from a different cause. It was fixed
# in the reason text above, not here: for `unknown_subject` the default headline
# is accurate, because that substance's evidence really was not found.)
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
