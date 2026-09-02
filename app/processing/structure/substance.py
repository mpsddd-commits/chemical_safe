"""Substance safety record structuring (화학물질안전관리정보, data.go.kr 15072442).

This source is not a 16-section MSDS document — it is one row per substance with
a paragraph of prose per exposure route. Run through the MSDS structurer it
matched nothing, so a substance came out as a single 542-token chunk with
`section_code = NULL`: every route of exposure blended into one passage that u2
could only cite as "this substance", never as "흡입 시" or "피부 접촉 시".

The routes are exactly the citation units a safety question asks about, so each
one becomes its own section — the same treatment accident records already get.

Labels are the logical names produced by `ConfiguredApiAdapter._project`; the
vendor's own names are listed too so a record that skipped the field map still
structures.
"""

from __future__ import annotations

from app.core.types import Section, StructureStatus
from app.processing.structure.record import find_sections as _find_record_sections

FIELDS: list[tuple[str, str, tuple[str, ...]]] = [
    # name_en comes first in the projected record; the identity section has to
    # start at whichever identity label appears first or the lines before it
    # fall outside every section and are never chunked (BR-26).
    ("substance_identity", "물질 식별",
     ("name_en", "chemEn", "name_ko", "chemKo", "물질명")),
    ("substance_symptom", "일반 증상", ("symptom", "증상")),
    ("substance_inhale", "흡입 시 영향", ("inhale", "흡입")),
    ("substance_skin", "피부 접촉 시 영향", ("skin", "피부")),
    ("substance_eye", "눈 접촉 시 영향", ("eyeball", "눈")),
    ("substance_oral", "경구 섭취 시 영향", ("oral", "경구", "섭취")),
    ("substance_etc", "그 밖의 정보", ("etc", "기타")),
]

# A substance row is only recognised as one when it carries at least one route
# of exposure. Identity alone is not enough: "name_ko:" could appear in any
# record, and mislabelling a document is worse than leaving it unstructured.
_REQUIRED_ANY = {"substance_symptom", "substance_inhale", "substance_skin",
                 "substance_eye", "substance_oral"}


def find_sections(text: str) -> tuple[list[Section], StructureStatus]:
    sections, status = _find_record_sections(text, FIELDS)
    if status is StructureStatus.UNSTRUCTURED:
        return sections, status
    if not any(s.section_code in _REQUIRED_ANY for s in sections):
        return [], StructureStatus.UNSTRUCTURED
    return sections, status
