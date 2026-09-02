"""C15 ChangeDetector (FR-7, BR-09~BR-11).

Content hash first, dates only as a fallback. Publishers revise documents
without always advancing a date field, so trusting the date alone would silently
skip real changes.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.types import SourceRef
from app.db.models import Document

log = get_logger(__name__)


class ChangeDetector:
    def has_changed(self, ref: SourceRef, known: Document | None) -> bool:
        if known is None:
            return True

        # BR-09 - hash wins whenever both sides have one.
        if ref.content_hash and known.content_hash:
            return ref.content_hash != known.content_hash

        # BR-10 - dates are the fallback, not the default.
        if ref.revised_at and known.revised_at:
            return ref.revised_at > known.revised_at
        if ref.published_at and known.published_at:
            return ref.published_at > known.published_at

        # Neither signal available: re-process rather than risk stale data.
        log.info(
            "change_undetermined_reprocessing",
            extra={"ref_key": ref.ref_key, "document_id": known.id},
        )
        return True
