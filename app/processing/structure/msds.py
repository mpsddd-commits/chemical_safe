"""MSDS 16-section structuring (BR-15~BR-20).

Section headers in real MSDS files vary a lot: numbering appears as "1.", "1)",
"제1항" or "Section 1", and titles are paraphrased. Matching on number *and* a
title keyword together is what keeps false positives low - a bare "3." inside a
paragraph is common, but "3. 구성성분의 명칭 및 함유량" is not.

When fewer than `MSDS_MIN_SECTIONS` sections are recognised the document is
marked `unstructured` and no section rows are written (BR-20). It still gets
indexed by paragraph (BR-28): a parsing miss must not become data loss.
"""

from __future__ import annotations

import re

from app.core.logging import get_logger
from app.core.types import Section, StructureStatus

log = get_logger(__name__)

# Canonical Korean titles for the 16 standard sections, with the keywords that
# identify each one. Keywords are matched case-insensitively against the header
# line following the number.
SECTION_KEYWORDS: dict[int, tuple[str, tuple[str, ...]]] = {
    1: ("화학제품과 회사에 관한 정보", ("화학제품", "제품명", "identification", "회사에 관한")),
    2: ("유해성·위험성", ("유해성", "위험성", "hazard")),
    3: ("구성성분의 명칭 및 함유량", ("구성성분", "함유량", "composition", "ingredient")),
    4: ("응급조치 요령", ("응급조치", "first aid", "first-aid")),
    5: ("폭발·화재시 대처방법", ("폭발", "화재", "fire", "fighting")),
    6: ("누출 사고시 대처방법", ("누출", "accidental release", "유출")),
    7: ("취급 및 저장방법", ("취급", "저장", "handling", "storage")),
    8: ("노출방지 및 개인보호구", ("노출방지", "개인보호구", "exposure control", "보호구")),
    9: ("물리화학적 특성", ("물리화학", "physical", "chemical propert")),
    10: ("안정성 및 반응성", ("안정성", "반응성", "stability", "reactivity")),
    11: ("독성에 관한 정보", ("독성", "toxicolog")),
    12: ("환경에 미치는 영향", ("환경", "ecolog")),
    13: ("폐기시 주의사항", ("폐기", "disposal")),
    14: ("운송에 필요한 정보", ("운송", "transport")),
    15: ("법적규제 현황", ("법적", "규제", "regulat")),
    16: ("그 밖의 참고사항", ("참고사항", "other information", "기타")),
}

# number + optional separator, at the start of a line
_HEADER = re.compile(
    r"^[ \t]*(?:제\s*)?(?P<num>1[0-6]|[1-9])\s*(?:[.)\]:·]|항|\s)\s*(?P<title>.{0,60})$",
    re.MULTILINE,
)


def _title_matches(number: int, title: str) -> bool:
    """BR-16 - the number alone is not enough; a title keyword must agree."""
    entry = SECTION_KEYWORDS.get(number)
    if entry is None:
        return False
    lowered = title.lower()
    return any(keyword.lower() in lowered for keyword in entry[1])


def find_sections(text: str, min_sections: int) -> tuple[list[Section], StructureStatus]:
    """Return recognised sections and the resulting structure status."""
    candidates: list[tuple[int, int]] = []  # (section number, start offset)
    seen: set[int] = set()

    for match in _HEADER.finditer(text):
        number = int(match.group("num"))
        title = (match.group("title") or "").strip()
        if not _title_matches(number, title):
            continue
        # BR-19 - a repeated section number keeps only its first occurrence.
        if number in seen:
            continue
        seen.add(number)
        candidates.append((number, match.start()))

    # BR-18 - gaps are fine; we keep whatever was actually recognised, in the
    # order it appears in the document.
    candidates.sort(key=lambda pair: pair[1])

    if len(candidates) < min_sections:
        return [], StructureStatus.UNSTRUCTURED

    # BR-20a - a two-column MSDS defeats text extraction: pypdf reads the right
    # column before the left, so the extracted text interleaves them. Measured on
    # real documents, 2 of 8 came out as msds_02, msds_01, msds_04, msds_03 ... -
    # section 3's chunk contained section 2's precautionary statements. The
    # headers are found correctly; the *body* under each one is not the body that
    # belongs to it, and u2 would cite it as though it were. Section numbers run
    # in ascending order in every real MSDS, so an inversion means the text is
    # not in document order and no label can be trusted.
    inversions = sum(
        1
        for index in range(1, len(candidates))
        if candidates[index][0] < candidates[index - 1][0]
    )
    if inversions:
        log.warning(
            "msds_sections_out_of_order",
            extra={
                "inversions": inversions,
                "order": [number for number, _ in candidates],
                "impact": "downgraded to unstructured; section labels would "
                "have been attached to the wrong text",
            },
        )
        return [], StructureStatus.UNSTRUCTURED

    sections: list[Section] = []
    for ordinal, (number, start) in enumerate(candidates):
        # BR-17 - a section runs to the next header, the last one to end of text.
        end = candidates[ordinal + 1][1] if ordinal + 1 < len(candidates) else len(text)
        if end <= start:
            continue
        sections.append(
            Section(
                ordinal=ordinal,
                section_code=f"msds_{number:02d}",
                section_title=SECTION_KEYWORDS[number][0],
                start_offset=start,
                end_offset=end,
            )
        )

    if len(sections) < min_sections:
        return [], StructureStatus.UNSTRUCTURED
    return sections, StructureStatus.STRUCTURED
