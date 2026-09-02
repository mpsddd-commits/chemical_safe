"""Statute structuring - article granularity (BR-21~BR-23).

The article (조) is the unit people cite and the unit that carries enough
context to answer a question. Splitting at the paragraph (항) level would give
sharper retrieval but would routinely strip the qualifying clause that makes an
obligation conditional - a bad trade in a compliance corpus.

Paragraph and item numbers are preserved *inside* the article chunk and listed
in metadata, so a citation can still say which paragraph it came from.
"""

from __future__ import annotations

import re

from app.core.types import Section, StructureStatus

# 제12조 / 제12조의2 , optionally followed by a parenthesised title
_ARTICLE = re.compile(
    r"^[ \t]*(?P<code>제\s*\d+\s*조(?:의\s*\d+)?)\s*(?:\((?P<title>[^)]{0,80})\))?",
    re.MULTILINE,
)
_ADDENDUM = re.compile(r"^[ \t]*(?P<code>부\s*칙)\b", re.MULTILINE)
_APPENDIX = re.compile(r"^[ \t]*(?P<code>\[?별표\s*\d*\]?)", re.MULTILINE)

# ①..⑳ and "제N항"
_CLAUSE_CIRCLED = re.compile(r"[①-⑳]")
# A 항 qualified by an article number belongs to *that* article, usually in
# another statute: "「폐기물관리법」 제25조제5항" made 제3조 claim a 제5항 it does
# not have (found against live data). A bare "제1항" is a self-reference within
# the same article and is still collected (NFR-8).
_CLAUSE_QUALIFIED = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?\s*제\s*\d+\s*항")
_CLAUSE_NUMBERED = re.compile(r"제\s*(\d+)\s*항")


def _normalize_code(raw: str) -> str:
    return re.sub(r"\s+", "", raw)


def find_sections(text: str) -> tuple[list[Section], StructureStatus]:
    marks: list[tuple[int, str, str | None]] = []

    for match in _ARTICLE.finditer(text):
        marks.append((match.start(), _normalize_code(match.group("code")),
                      (match.group("title") or "").strip() or None))
    # BR-23 - addenda and appendices are separate sections, not part of the last
    # article. Folding them in would make an article chunk claim text that is not
    # its own.
    for match in _ADDENDUM.finditer(text):
        marks.append((match.start(), "부칙", None))
    for match in _APPENDIX.finditer(text):
        marks.append((match.start(), _normalize_code(match.group("code")), None))

    if not marks:
        return [], StructureStatus.UNSTRUCTURED

    marks.sort(key=lambda m: m[0])
    # drop duplicate offsets produced by overlapping patterns
    deduped: list[tuple[int, str, str | None]] = []
    for mark in marks:
        if deduped and mark[0] == deduped[-1][0]:
            continue
        deduped.append(mark)

    sections: list[Section] = []
    for ordinal, (start, code, title) in enumerate(deduped):
        end = deduped[ordinal + 1][0] if ordinal + 1 < len(deduped) else len(text)
        if end <= start:
            continue
        sections.append(
            Section(
                ordinal=len(sections),
                section_code=code,
                section_title=title,
                start_offset=start,
                end_offset=end,
            )
        )

    if not sections:
        return [], StructureStatus.UNSTRUCTURED
    return sections, StructureStatus.STRUCTURED


def clause_numbers(article_text: str) -> list[str]:
    """BR-22 - paragraph numbers kept as metadata on the article chunk."""
    found: list[str] = []
    for ch in _CLAUSE_CIRCLED.findall(article_text):
        found.append(str(ord(ch) - 0x2460 + 1))
    # Drop qualified references before scanning so only this article's own
    # paragraph numbers remain.
    found.extend(_CLAUSE_NUMBERED.findall(_CLAUSE_QUALIFIED.sub(" ", article_text)))
    seen: set[str] = set()
    ordered: list[str] = []
    for number in found:
        if number not in seen:
            seen.add(number)
            ordered.append(number)
    return ordered
