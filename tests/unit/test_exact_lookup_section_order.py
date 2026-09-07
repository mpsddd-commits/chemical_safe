"""A typed CAS and a resolved name must order a record the same way.

`_resolved_record_chunks` has read the question's wording since BR-65a: an
inhalation question gets `substance_inhale` in front. `lookup_exact` (BR-38)
never did, so "염소를 흡입하면" and "CAS 7782-50-5 물질을 흡입하면" - the same
question - reached two different orderings, and the CAS one always led with
`substance_identity` because that is the record's `ordinal 0`.

The asymmetry is older than the round robin. What run 607 did was remove the
arbitrary order that had been covering it: sub-07's MRR 1.000 in run 606 was an
unordered LIMIT happening to hand back the inhalation chunk first, not a
ranking. Measured 607: sub-04 0.500 -> 0.333, sub-07 1.000 -> 0.500.
"""

from __future__ import annotations

from app.core.types import Scope
from app.indexing.keyword_index import EXACT_MATCH_SCORE, KeywordIndex
from app.indexing.vector_index import MetaFilter

# ordinal order of a substance record. `substance_identity` at 0 is the chunk
# that led every typed-CAS lookup regardless of what the question asked.
RECORD_SECTIONS = (
    "substance_identity",
    "substance_symptom",
    "substance_inhale",
    "substance_skin",
    "substance_eye",
    "substance_oral",
    "substance_first_aid",
)


def _record_rows(document_id: int = 86) -> list[tuple[int, int, str]]:
    return [
        (document_id * 1000 + ordinal, document_id, section)
        for ordinal, section in enumerate(RECORD_SECTIONS)
    ]


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _RowsSession:
    def __init__(self, rows) -> None:
        self._rows = rows

    def execute(self, statement):
        return _Result(self._rows)


class _FirstStatementSession:
    """Answers the exact fetch and nothing else.

    `search` issues the identifier lookup first; the full-text statement that
    follows is not what this file is about, and an empty result keeps it out of
    the way without a database.
    """

    def __init__(self, rows) -> None:
        self._rows = rows
        self.calls = 0

    def execute(self, statement):
        self.calls += 1
        return _Result(self._rows if self.calls == 1 else [])


class TestPreferredSectionLeadsItsDocument:
    def test_inhalation_question_puts_the_inhalation_chunk_first(self):
        """sub-07 - evidence is `substance_inhale`, ordinal 2."""
        index = KeywordIndex(_RowsSession(_record_rows()))

        candidates = index.lookup_exact(
            "7782-50-5",
            "cas_number",
            Scope.public(),
            limit=30,
            preferred_sections=frozenset({"substance_inhale"}),
        )

        assert candidates[0].chunk_id == 86002

    def test_swallowing_question_puts_the_oral_chunk_first(self):
        """sub-04 - evidence is `substance_oral`, ordinal 5, the last route."""
        index = KeywordIndex(_RowsSession(_record_rows()))

        candidates = index.lookup_exact(
            "67-56-1",
            "cas_number",
            Scope.public(),
            limit=30,
            preferred_sections=frozenset({"substance_oral"}),
        )

        assert candidates[0].chunk_id == 86005

    def test_unpreferred_chunks_are_kept_in_ordinal_order_behind(self):
        """BR-38 is a lookup, not a shortlist - nothing is dropped.

        `_resolved_record_chunks` keeps three because a name resolves to the
        record without the user asking for it. A typed identifier is the user
        asking, so the reorder must be a reorder only.
        """
        index = KeywordIndex(_RowsSession(_record_rows()))

        candidates = index.lookup_exact(
            "7782-50-5",
            "cas_number",
            Scope.public(),
            limit=30,
            preferred_sections=frozenset({"substance_inhale"}),
        )

        assert [c.chunk_id for c in candidates] == [
            86002, 86000, 86001, 86003, 86004, 86005, 86006,
        ]

    def test_two_preferred_sections_keep_their_ordinal_order(self):
        """The sort is stable, so preference is a partition, not a new ranking."""
        index = KeywordIndex(_RowsSession(_record_rows()))

        candidates = index.lookup_exact(
            "7782-50-5",
            "cas_number",
            Scope.public(),
            limit=30,
            preferred_sections=frozenset({"substance_oral", "substance_symptom"}),
        )

        assert [c.chunk_id for c in candidates][:2] == [86001, 86005]

    def test_documents_keep_their_turn_order(self):
        """Reordering inside a document must not disturb the round robin."""
        rows = _record_rows(86) + _record_rows(90)
        index = KeywordIndex(_RowsSession(rows))

        candidates = index.lookup_exact(
            "7782-50-5",
            "cas_number",
            Scope.public(),
            limit=30,
            preferred_sections=frozenset({"substance_inhale"}),
        )

        assert [c.chunk_id for c in candidates][:4] == [86002, 90002, 86000, 90000]

    def test_every_hit_still_carries_the_exact_match_score(self):
        index = KeywordIndex(_RowsSession(_record_rows()))

        candidates = index.lookup_exact(
            "7782-50-5",
            "cas_number",
            Scope.public(),
            limit=30,
            preferred_sections=frozenset({"substance_inhale"}),
        )

        assert {c.score for c in candidates} == {EXACT_MATCH_SCORE}


class TestNoPreferredSectionChangesNothing:
    """sub-01 is the question that decides whether this design is right.

    "CAS 7664-93-9 물질은 무엇인가요?" matches no route pattern and no MSDS
    topic, so the preferred set is empty - and `substance_identity` at ordinal 0
    is exactly the right answer for it. If preference-free lookup moved at all,
    the fix would be trading sub-01 away for sub-04 and sub-07.
    """

    def test_ordinal_order_is_untouched(self):
        index = KeywordIndex(_RowsSession(_record_rows()))

        candidates = index.lookup_exact("7664-93-9", "cas_number", Scope.public(), limit=30)

        assert [c.chunk_id for c in candidates] == [
            86000, 86001, 86002, 86003, 86004, 86005, 86006,
        ]

    def test_identity_leads_when_the_question_asks_what_it_is(self):
        index = KeywordIndex(_RowsSession(_record_rows()))

        candidates = index.lookup_exact(
            "7664-93-9",
            "cas_number",
            Scope.public(),
            limit=30,
            preferred_sections=frozenset(),
        )

        assert candidates[0].chunk_id == 86000

    def test_the_default_is_no_preference(self):
        """Existing callers pass four arguments and must keep their behaviour."""
        with_default = KeywordIndex(_RowsSession(_record_rows())).lookup_exact(
            "7664-93-9", "cas_number", Scope.public(), limit=30
        )
        explicit = KeywordIndex(_RowsSession(_record_rows())).lookup_exact(
            "7664-93-9",
            "cas_number",
            Scope.public(),
            limit=30,
            preferred_sections=frozenset(),
        )
        assert [c.chunk_id for c in with_default] == [c.chunk_id for c in explicit]

    def test_a_section_nothing_matches_is_inert(self):
        """A preference the document does not hold leaves the order alone."""
        index = KeywordIndex(_RowsSession(_record_rows()))

        candidates = index.lookup_exact(
            "7664-93-9",
            "cas_number",
            Scope.public(),
            limit=30,
            preferred_sections=frozenset({"msds_07"}),
        )

        assert [c.chunk_id for c in candidates] == [
            86000, 86001, 86002, 86003, 86004, 86005, 86006,
        ]


class TestSearchFeedsTheQuestionThrough:
    """The wiring: `search` must read the wording the same way both paths do."""

    def test_a_typed_cas_inhalation_question_reaches_the_inhalation_chunk(self):
        session = _FirstStatementSession(_record_rows())
        index = KeywordIndex(session)

        candidates = index.search(
            "CAS 7782-50-5 물질을 흡입하면 어떻게 되나요?",
            top_k=10,
            filters=MetaFilter(),
            scope=Scope.public(),
        )

        assert candidates[0].chunk_id == 86002

    def test_a_typed_cas_swallowing_question_reaches_the_oral_chunk(self):
        session = _FirstStatementSession(_record_rows())
        index = KeywordIndex(session)

        candidates = index.search(
            "CAS 67-56-1 물질을 삼켰을 때 보통 치명적인 양은 얼마인가요?",
            top_k=10,
            filters=MetaFilter(),
            scope=Scope.public(),
        )

        assert candidates[0].chunk_id == 86005

    def test_an_unrouted_question_still_reaches_identity(self):
        """sub-01, through `search` rather than through `lookup_exact` alone."""
        session = _FirstStatementSession(_record_rows())
        index = KeywordIndex(session)

        candidates = index.search(
            "CAS 7664-93-9 물질은 무엇인가요?",
            top_k=10,
            filters=MetaFilter(),
            scope=Scope.public(),
        )

        assert candidates[0].chunk_id == 86000


class TestOrderingIsDeterministic:
    def test_the_same_rows_give_the_same_list(self):
        rows = _record_rows(86) + _record_rows(90)
        preferred = frozenset({"substance_inhale"})
        first = KeywordIndex(_RowsSession(rows)).lookup_exact(
            "7782-50-5", "cas_number", Scope.public(), limit=30, preferred_sections=preferred
        )
        second = KeywordIndex(_RowsSession(rows)).lookup_exact(
            "7782-50-5", "cas_number", Scope.public(), limit=30, preferred_sections=preferred
        )
        assert [c.chunk_id for c in first] == [c.chunk_id for c in second]

    def test_the_fetch_bound_is_unchanged(self):
        """`_EXACT_FETCH_MULTIPLIER` still decides how much the reorder sees."""

        class _Recording(_RowsSession):
            def __init__(self, rows):
                super().__init__(rows)
                self.statements = []

            def execute(self, statement):
                self.statements.append(statement)
                return super().execute(statement)

        session = _Recording(_record_rows())
        KeywordIndex(session).lookup_exact(
            "7782-50-5",
            "cas_number",
            Scope.public(),
            limit=30,
            preferred_sections=frozenset({"substance_inhale"}),
        )

        assert session.statements[0]._limit == 300
