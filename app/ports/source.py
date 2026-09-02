"""C5 SourceAdapter - the only thing the ingestion orchestrator knows about a
data source (DD-2). Adding a new source means adding an implementation, not
touching the orchestrator.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.core.types import RawDocument, SourceRef


@runtime_checkable
class SourceAdapter(Protocol):
    def source_id(self) -> str:
        """Logical identifier matching `source.source_id`."""
        ...

    def list_targets(self, since: datetime | None) -> Iterator[SourceRef]:
        """Enumerate collectable documents, optionally restricted to changes
        after `since` (FR-7)."""
        ...

    def fetch(self, ref: SourceRef) -> RawDocument:
        """Retrieve one document. Raises TransientError / PermanentError from
        app.core.errors so the retry policy can classify it (BR-41, BR-42)."""
        ...
