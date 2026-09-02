"""Chemical accident record structuring (BR-25).

Incident records arrive as flat key/value data that `extract` has already
rendered as "label: value" lines. Each known field becomes one section; absent
fields produce no section at all rather than an empty one, so a chunk never
claims to describe damage that was never reported (NFR-8).

The labels are the *logical* field names produced by `ConfiguredApiAdapter.
_project`, not the vendor's physical names. The vendor names are listed too so
that a hand-assembled record or a source whose field map is incomplete still
structures.
"""

from __future__ import annotations

from app.core.types import Section, StructureStatus
from app.processing.structure.record import find_sections as _find_record_sections

# logical field -> (section code, display title, label patterns)
FIELDS: list[tuple[str, str, tuple[str, ...]]] = [
    ("incident_when", "발생 일시", ("occurred_at", "accidentDate", "cscDe", "발생일")),
    ("incident_type", "사고 유형", ("incident_type", "cscTy", "사고유형")),
    ("incident_area", "발생 지역", ("area", "지역")),
    ("incident_where", "발생 장소", ("place", "accidentPlace", "발생장소")),
    ("incident_substance", "관련 물질", ("substances", "chemName", "chem", "물질")),
    ("incident_cause", "사고 원인", ("cause", "accidentCause", "원인")),
    ("incident_damage", "피해 내용", ("damage", "damageDetail", "피해")),
    ("incident_action", "조치 사항", ("action", "emergencyAction", "조치")),
    ("incident_summary", "사고 개요", ("summary", "accidentSummary", "사고개요", "개요")),
]


def find_sections(text: str) -> tuple[list[Section], StructureStatus]:
    """Sections run from one label to the next — see `record.find_sections`."""
    return _find_record_sections(text, FIELDS)
