"""Defect 59 - an unordered LIMIT decided which CAS chunks survived.

`lookup_exact` used to be `select(...).limit(limit)` with no `ORDER BY`. The
rows PostgreSQL happened to return filled the 30 slots of `keyword_top_k`, and
on 2026-09-07 (run 606) two vendor MSDS documents of 16 and 14 chunks filled
them exactly - the substance record for the same CAS never entered the keyword
list, and sub-01 went from 1.000 to 0.000 on Recall@5, Recall@10 and MRR.

These tests pin the two properties the round robin owes: a document that is not
first does not disappear, and the same matching set yields the same list.
"""

from __future__ import annotations

from app.core.types import Scope
from app.indexing.keyword_index import EXACT_MATCH_SCORE, KeywordIndex


class _RecordingSession:
    """Returns a fixed row set and remembers the statement it was given."""

    def __init__(self, rows: list[tuple[int, int, str]]) -> None:
        self._rows = rows
        self.statements: list[object] = []

    def execute(self, statement):
        self.statements.append(statement)
        return _Result(self._rows)


class _Result:
    def __init__(self, rows: list[tuple[int, int, str]]) -> None:
        self._rows = rows

    def all(self):
        return list(self._rows)


# The fixed shape of a substance record, `ordinal` order. `substance_identity`
# is ordinal 0, which is why an unrouted fetch leads with it.
RECORD_SECTIONS = (
    "substance_identity",
    "substance_symptom",
    "substance_inhale",
    "substance_skin",
    "substance_eye",
    "substance_oral",
    "substance_first_aid",
)


def _corpus() -> list[tuple[int, int, str]]:
    """The run-606 shape: (chunk_id, document_id, section_code) by document, ordinal.

    Document 20 has 16 chunks, document 21 has 14 - 30 between them, exactly
    `keyword_top_k` - and document 86 is the seven-chunk substance record.
    """
    rows: list[tuple[int, int, str]] = []
    for document_id, count in ((20, 16), (21, 14)):
        rows.extend(
            (document_id * 1000 + ordinal, document_id, f"msds_{ordinal + 1:02d}")
            for ordinal in range(count)
        )
    rows.extend(
        (86000 + ordinal, 86, section) for ordinal, section in enumerate(RECORD_SECTIONS)
    )
    return rows


class TestRoundRobinKeepsEveryDocument:
    def test_substance_record_survives_a_full_budget(self):
        """Two MSDS filling all 30 slots is the measured accident."""
        session = _RecordingSession(_corpus())
        index = KeywordIndex(session)

        candidates = index.lookup_exact("7664-93-9", "cas_number", Scope.public(), limit=30)

        documents = {chunk_id // 1000 for chunk_id in (c.chunk_id for c in candidates)}
        assert documents == {20, 21, 86}

    def test_turns_alternate_by_document_id_ascending(self):
        session = _RecordingSession(_corpus())
        index = KeywordIndex(session)

        candidates = index.lookup_exact("7664-93-9", "cas_number", Scope.public(), limit=30)

        assert [c.chunk_id for c in candidates[:6]] == [
            20000, 21000, 86000,
            20001, 21001, 86001,
        ]

    def test_budget_is_still_respected(self):
        session = _RecordingSession(_corpus())
        index = KeywordIndex(session)

        candidates = index.lookup_exact("7664-93-9", "cas_number", Scope.public(), limit=30)

        assert len(candidates) == 30

    def test_no_document_is_capped_short_while_slots_remain(self):
        """A per-document hard cap would cut the MSDS sections a question needs.

        Document 20's sixteenth chunk is reachable here because the budget is
        larger than the corpus, and it must stay reachable.
        """
        session = _RecordingSession(_corpus())
        index = KeywordIndex(session)

        candidates = index.lookup_exact("7664-93-9", "cas_number", Scope.public(), limit=50)

        assert len(candidates) == 37
        assert 20015 in {c.chunk_id for c in candidates}

    def test_every_hit_keeps_the_exact_match_score(self):
        """BR-38 - the round robin reorders, it does not re-score."""
        session = _RecordingSession(_corpus())
        index = KeywordIndex(session)

        candidates = index.lookup_exact("7664-93-9", "cas_number", Scope.public(), limit=30)

        assert {c.score for c in candidates} == {EXACT_MATCH_SCORE}
        assert {c.route for c in candidates} == {"keyword"}


class TestRoundRobinIsDeterministic:
    def test_same_input_same_output(self):
        rows = _corpus()
        first = KeywordIndex(_RecordingSession(rows)).lookup_exact(
            "7664-93-9", "cas_number", Scope.public(), limit=30
        )
        second = KeywordIndex(_RecordingSession(rows)).lookup_exact(
            "7664-93-9", "cas_number", Scope.public(), limit=30
        )
        assert [c.chunk_id for c in first] == [c.chunk_id for c in second]

    def test_which_documents_appear_never_depends_on_row_order(self):
        """The old code's answer was whatever order the rows arrived in.

        The `ORDER BY` fixes which chunk of a document comes first, so a
        shuffled row set legitimately picks different chunks. What must not
        move is *which documents get a turn* - that is the half that dropped
        document 86 on the floor.
        """
        rows = _corpus()
        for arrival in (rows, list(reversed(rows)), sorted(rows, key=lambda r: r[0] % 7)):
            candidates = KeywordIndex(_RecordingSession(arrival)).lookup_exact(
                "7664-93-9", "cas_number", Scope.public(), limit=30
            )
            assert sorted({c.chunk_id // 1000 for c in candidates}) == [20, 21, 86]


class TestExactLookupStatement:
    def test_the_fetch_is_ordered_and_bounded(self):
        """No ORDER BY is the defect itself; no bound is a full scan."""
        session = _RecordingSession(_corpus())
        KeywordIndex(session).lookup_exact("7664-93-9", "cas_number", Scope.public(), limit=30)

        compiled = str(session.statements[0])
        assert "ORDER BY chunk.document_id, chunk.ordinal" in compiled
        assert session.statements[0]._limit == 300

    def test_unsupported_field_still_raises(self):
        session = _RecordingSession([])
        try:
            KeywordIndex(session).lookup_exact("x", "section_code", Scope.public())
        except ValueError as error:
            assert "section_code" in str(error)
        else:  # pragma: no cover - the guard is the assertion
            raise AssertionError("unsupported field must raise")
