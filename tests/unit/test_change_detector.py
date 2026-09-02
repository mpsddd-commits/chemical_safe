"""Change detection — BR-09, BR-10, BR-11."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.core.types import SourceRef
from app.ingestion.change_detector import ChangeDetector


@dataclass
class FakeDocument:
    id: int = 1
    content_hash: str | None = None
    published_at: datetime | None = None
    revised_at: datetime | None = None


def _ref(**kwargs) -> SourceRef:
    defaults = {
        "source_id": "src",
        "external_id": "doc-1",
        "url": "https://example.test/doc-1",
    }
    defaults.update(kwargs)
    return SourceRef(**defaults)


@pytest.fixture
def detector() -> ChangeDetector:
    return ChangeDetector()


class TestHashFirst:
    def test_new_document_is_always_a_change(self, detector):
        assert detector.has_changed(_ref(content_hash="abc"), None) is True

    def test_same_hash_is_unchanged(self, detector):
        known = FakeDocument(content_hash="abc")
        assert detector.has_changed(_ref(content_hash="abc"), known) is False

    def test_different_hash_is_changed(self, detector):
        known = FakeDocument(content_hash="abc")
        assert detector.has_changed(_ref(content_hash="def"), known) is True

    def test_hash_beats_dates(self, detector):
        """BR-09 — publishers revise content without moving the date field.

        Same date, different hash: this must be treated as changed.
        """
        when = datetime(2024, 1, 1, tzinfo=UTC)
        known = FakeDocument(content_hash="abc", revised_at=when)
        ref = _ref(content_hash="def", revised_at=when)
        assert detector.has_changed(ref, known) is True

    def test_same_hash_wins_even_if_date_moved(self, detector):
        known = FakeDocument(content_hash="abc", revised_at=datetime(2024, 1, 1, tzinfo=UTC))
        ref = _ref(content_hash="abc", revised_at=datetime(2025, 1, 1, tzinfo=UTC))
        assert detector.has_changed(ref, known) is False


class TestDateFallback:
    def test_newer_revision_date_is_a_change(self, detector):
        known = FakeDocument(revised_at=datetime(2024, 1, 1, tzinfo=UTC))
        ref = _ref(revised_at=datetime(2024, 6, 1, tzinfo=UTC))
        assert detector.has_changed(ref, known) is True

    def test_same_revision_date_is_unchanged(self, detector):
        when = datetime(2024, 1, 1, tzinfo=UTC)
        assert detector.has_changed(_ref(revised_at=when), FakeDocument(revised_at=when)) is False

    def test_older_revision_date_is_unchanged(self, detector):
        known = FakeDocument(revised_at=datetime(2025, 1, 1, tzinfo=UTC))
        ref = _ref(revised_at=datetime(2024, 1, 1, tzinfo=UTC))
        assert detector.has_changed(ref, known) is False

    def test_published_date_used_when_revision_absent(self, detector):
        known = FakeDocument(published_at=datetime(2024, 1, 1, tzinfo=UTC))
        ref = _ref(published_at=datetime(2024, 6, 1, tzinfo=UTC))
        assert detector.has_changed(ref, known) is True


class TestNoSignal:
    def test_reprocesses_when_nothing_can_be_compared(self, detector):
        """With no hash and no dates, stale data is the worse failure."""
        assert detector.has_changed(_ref(), FakeDocument()) is True

    def test_partial_hash_falls_through_to_dates(self, detector):
        known = FakeDocument(content_hash=None, revised_at=datetime(2024, 1, 1, tzinfo=UTC))
        ref = _ref(content_hash="abc", revised_at=datetime(2024, 1, 1, tzinfo=UTC))
        assert detector.has_changed(ref, known) is False
