"""C21 StructureStage - dispatch by document type (BR-24).

This stage never fails the pipeline. A document whose structure could not be
recognised is marked `unstructured` and continues to chunking, where it is split
by paragraph (BR-28). Losing section metadata is acceptable; losing the document
is not.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.types import DocType, StructuredDoc, StructureStatus
from app.processing.structure import incident as incident_structure
from app.processing.structure import law as law_structure
from app.processing.structure import msds as msds_structure
from app.processing.structure import substance as substance_structure

log = get_logger(__name__)


def structure(text: str, doc_type: DocType, settings: Settings | None = None) -> StructuredDoc:
    settings = settings or get_settings()
    try:
        if doc_type is DocType.SUBSTANCE:
            # Its own type since 2026-08-30, so this no longer arrives here by
            # way of a failed MSDS parse.
            sections, status = substance_structure.find_sections(text)
        elif doc_type is DocType.MSDS or doc_type is DocType.USER_UPLOAD:
            sections, status = msds_structure.find_sections(text, settings.msds_min_sections)
            if status is StructureStatus.UNSTRUCTURED:
                # The fallback stays for uploads: a user's PDF may be a substance
                # record rather than a 16-section datasheet, and we do not get to
                # declare which. Collected substance records take the branch above.
                sections, status = substance_structure.find_sections(text)
        elif doc_type is DocType.LAW:
            sections, status = law_structure.find_sections(text)
        elif doc_type is DocType.INCIDENT:
            sections, status = incident_structure.find_sections(text)
        else:
            sections, status = [], StructureStatus.UNSTRUCTURED
    except Exception as exc:  # noqa: BLE001 - BR-24: never abort on a parse error
        log.warning("structure_failed_falling_back", exc_info=exc,
                    extra={"doc_type": doc_type.value})
        sections, status = [], StructureStatus.UNSTRUCTURED

    if status is StructureStatus.UNSTRUCTURED:
        log.info(
            "document_unstructured",
            extra={"doc_type": doc_type.value, "reason": "section detection below threshold"},
        )
    return StructuredDoc(doc_type=doc_type, sections=sections, structure_status=status)
