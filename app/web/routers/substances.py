"""Substance routes - P7 and P7-1 (FR-23~26, FR-45).

Plain JSON, not SSE (FQ4-14): there is nothing to stream. The card is a
structured lookup with no LLM in the path, which is also why NFR-3's one-second
budget is comfortable and why the free tier's daily quota does not reach this
unit at all.

⚠️ Like `/admin` and `/usage`, these screens have no authentication until u5.
Loopback binding (NFR-18) is the only control.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.types import AuthenticatedUser
from app.services.substance_service import SubstanceService
from app.substances.types import NO_DATA, SubstanceCard, SubstanceRef
from app.web.deps import current_user
from app.web.routers.api import get_session

router = APIRouter(tags=["substances"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

MAX_QUERY_CHARS = 200

# Shown next to a candidate so the user can see *why* it is one (BR-101).
MATCH_LABEL = {
    "cas": "CAS 일치",
    "un": "UN 일치",
    "name_ko": "국문명 일치",
    "name_en": "영문명 일치",
    "alias": "이명 일치",
}


def _clean_query(raw: str | None) -> str:
    return (raw or "").strip()[:MAX_QUERY_CHARS]


def _ref_dict(ref: SubstanceRef) -> dict:
    return {
        "substance_id": ref.substance_id,
        "cas_number": ref.cas_number,
        "name_ko": ref.name_ko,
        "name_en": ref.name_en,
        "matched_on": ref.matched_on.value,
    }


def _card_dict(card: SubstanceCard) -> dict:
    return {
        "substance": _ref_dict(card.substance),
        "has_msds": card.has_msds,
        # BR-106 - the gap count ships with the card so no consumer can present
        # it as complete by omission.
        "missing_count": card.missing_count,
        "items": [
            {
                "key": item.key.value,
                "label": item.label,
                # An empty list is a normal state, not an error: most of the 40
                # substances have no MSDS (BR-102).
                "values": [
                    {
                        "text": value.text,
                        "document_id": value.document_id,
                        "document_title": value.document_title,
                        "section_code": value.section_code,
                        "section_title": value.section_title,
                        "source_url": value.source_url,
                        "origin": value.origin.value,
                        "route": value.route.value if value.route else None,
                    }
                    for value in item.values
                ],
            }
            for item in card.items
        ],
    }


@router.get("/api/substances")
def search_json(
    q: str = Query(default=""),
    session: Session = Depends(get_session),
) -> dict:
    matches, unsupported = SubstanceService(session).search(_clean_query(q))
    return {
        "query": _clean_query(q),
        "matches": [_ref_dict(m) for m in matches],
        # BR-109/110 - travels with every response so a client cannot quietly
        # omit that UN numbers and aliases have no data behind them.
        "unsupported_keys": list(unsupported),
    }


@router.get("/api/substances/{substance_id}")
def card_json(substance_id: int, session: Session = Depends(get_session)) -> dict:
    card = SubstanceService(session).card(substance_id)
    if card is None:
        raise HTTPException(status_code=404, detail="substance not found")
    return _card_dict(card)


@router.get("/substances", response_class=HTMLResponse)
def search_page(
    request: Request,
    q: str | None = Query(default=None),
    session: Session = Depends(get_session),
    user: AuthenticatedUser | None = Depends(current_user),
) -> HTMLResponse:
    query = _clean_query(q)
    matches: list[SubstanceRef] = []
    unsupported: tuple[str, ...] = ()
    if query:
        matches, unsupported = SubstanceService(session).search(query)

    # One match still goes to the list rather than redirecting: with a substring
    # search, "one result today" can become "three results tomorrow", and a page
    # that sometimes redirects is harder to trust than one that never does.
    return templates.TemplateResponse(
        request,
        "substances.html",
        {
            "active": "substances",
            "user": user,
            "query": query,
            "searched": bool(query),
            "matches": matches,
            "unsupported_keys": list(unsupported),
            "match_label": MATCH_LABEL,
        },
    )


@router.get("/substances/{substance_id}", response_class=HTMLResponse)
def card_page(
    request: Request, substance_id: int, session: Session = Depends(get_session)
) -> HTMLResponse:
    card = SubstanceService(session).card(substance_id)
    if card is None:
        raise HTTPException(status_code=404, detail="substance not found")
    return templates.TemplateResponse(
        request,
        "substance_card.html",
        {"active": "substances", "card": card, "no_data": NO_DATA},
    )
