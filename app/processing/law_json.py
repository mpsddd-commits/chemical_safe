"""Render 국가법령정보 statute JSON as text the law structurer can read.

The API already decomposes a statute into 조 / 항 / 호, which is exactly the
decomposition `structure/law.py` reconstructs with regexes. Throwing that away
and flattening the JSON generically produced one 95,000-character chunk with
zero articles detected, because every line came out prefixed with "법령: " and
the `^제N조` anchor never matched.

Rendering happens at extract time rather than in the adapter so the retained
original stays the untouched API response (FQ-8=A): when this rendering changes,
re-indexing applies it without re-collecting from the source.

`조문내용`, `항내용` and `호내용` already carry their own numbering ("제3조(적용범위)",
"① ...", "1. ..."), so rendering is concatenation in document order - nothing is
renumbered or invented (NFR-8).
"""

from __future__ import annotations

from typing import Any


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _render_clauses(hang: Any, lines: list[str]) -> None:
    """항 -> 호 -> 목, each already numbered by the source."""
    for paragraph in _as_list(hang):
        if not isinstance(paragraph, dict):
            body = _text(paragraph)
            if body:
                lines.append(body)
            continue
        body = _text(paragraph.get("항내용"))
        if body:
            lines.append(body)
        for item in _as_list(paragraph.get("호")):
            if not isinstance(item, dict):
                continue
            item_body = _text(item.get("호내용"))
            if item_body:
                lines.append(item_body)
            for sub in _as_list(item.get("목")):
                if isinstance(sub, dict):
                    sub_body = _text(sub.get("목내용"))
                    if sub_body:
                        lines.append(sub_body)


def render_statute(payload: Any) -> str | None:
    """Return statute text, or None when this is not a statute response.

    Returning None rather than raising keeps the generic JSON path intact for
    every other source.
    """
    if not isinstance(payload, dict):
        return None
    law = payload.get("법령")
    if not isinstance(law, dict):
        return None
    units = _as_list((law.get("조문") or {}).get("조문단위"))
    addenda = _as_list((law.get("부칙") or {}).get("부칙단위"))
    if not units and not addenda:
        return None

    lines: list[str] = []
    info = law.get("기본정보") or {}
    title = _text(info.get("법령명_한글"))
    if title:
        lines.append(title)

    for unit in units:
        if not isinstance(unit, dict):
            continue
        # 조문여부 == "전문" marks a chapter heading (제1장 총칙); it is kept
        # because it gives the articles under it their context, and the
        # structurer simply will not match it as an article.
        body = _text(unit.get("조문내용"))
        if body:
            lines.append(body)
        _render_clauses(unit.get("항"), lines)

    for addendum in addenda:
        if not isinstance(addendum, dict):
            continue
        for key in ("부칙내용", "부칙제목"):
            for chunk in _as_list(addendum.get(key)):
                body = _text(chunk if not isinstance(chunk, list) else " ".join(map(str, chunk)))
                if body:
                    lines.append(body)

    # A blank line between articles: the chunker can only split an oversized
    # section at a paragraph boundary (BR-27), and without one a long statute
    # cannot be split at all.
    return "\n\n".join(lines) if lines else None
