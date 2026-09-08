"""C14 — a filtered sentence must keep the evidence it was judged against.

Measured 2026-09-08 on query 484, with no quota contamination. One evidence
chunk held these bullets

    eyeball: ·눈에 소량은 영구적은 손상을 일으킬 것임
    ·또한 동상을 일으킬 것임
    ·증기상 물질은 화상과 자극을 일으킴
    ·찬 증기는 동상을 일으킬 수 있음
    ·홍반. 통증. 심한 깊은 화상

and the five generated sentences mapped almost one-to-one onto them. Four came
back `unsupported`. Two explanations fit that equally well — the generator cited
some other substance's chunk (in which case `verify_one`, which sees only the
sentence's own `chunk_ids`, was right), or the verifier is too strict — and the
stored rows separated neither, because the filtered sentences were written with
`citations=[]`.

C11 stored the filtered *sentences* for the same reason: BR-88, a count with no
rows behind it cannot be audited. This is that rule one level down. A verdict
with no evidence behind it cannot be audited either, and the `citation_snapshot`
is the only place the text the verifier actually saw is kept.

The other half of these tests is that none of it is passed off as the answer.
The answer path and the history counts carry only what was read. The audit
endpoint carries everything, and marks which is which — the reading it would
otherwise invite, "these are the sources of what you were told", is the one
reading that would be false.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.auth.types import AuthenticatedUser
from app.core.types import AnswerOutcome, SupportVerdict
from app.db.models import AnswerCitationRow, AnswerSentenceRow, CitationSnapshotRow
from app.rag.citations import citations_for_answer
from app.rag.types import AnswerSentence
from app.services.account_service import AccountService
from tests.unit.test_refusal_keeps_its_sentences import (
    FakeSession,
    _evidence,
    _service,
    _stored,
)


def _citations(content: FakeSession) -> list[AnswerCitationRow]:
    return [row for row in content.added if isinstance(row, AnswerCitationRow)]


def _snapshots(content: FakeSession) -> list[CitationSnapshotRow]:
    return [row for row in content.added if isinstance(row, CitationSnapshotRow)]


def _by_sentence(content: FakeSession, sentence: AnswerSentenceRow):
    return [c for c in _citations(content) if c.sentence_id == sentence.id]


class TestTheRefusalPathStoresWhatItJudgedAgainst:
    """Every sentence was filtered, so the query refused — query 484's shape."""

    def test_a_filtered_sentence_keeps_its_citation(self):
        sentences = [
            AnswerSentence(text="암모니아는 눈에 동상을 일으킬 수 있습니다.", chunk_ids=[11]),
            AnswerSentence(text="찬 암모니아 증기는 눈에 동상을 일으킵니다.", chunk_ids=[11]),
        ]
        service, content = _service(
            sentences, [SupportVerdict.UNSUPPORTED, SupportVerdict.UNSUPPORTED]
        )

        result = service.answer("암모니아가 눈에 닿으면?")

        assert result.outcome is AnswerOutcome.REFUSED_UNSUPPORTED
        rows = _stored(content)
        assert all(r.removed is True for r in rows)
        assert [len(_by_sentence(content, r)) for r in rows] == [1, 1]
        assert {c.chunk_id for c in _citations(content)} == {11}

    def test_the_snapshot_holds_the_text_the_verifier_was_shown(self):
        """The point of the whole change. Without this the reader of a false
        `unsupported` has the sentence and the verdict and no way to see what
        the sentence was compared with."""
        service, content = _service(
            [AnswerSentence(text="암모니아 증기는 화상을 일으킵니다.", chunk_ids=[11])],
            [SupportVerdict.UNSUPPORTED],
        )

        service.answer("암모니아 증기?")

        assert [s.snippet for s in _snapshots(content)] == [_evidence().text]

    def test_a_sentence_citing_nothing_we_hold_stores_no_citation(self):
        """`verify_one` calls this `unsupported` for lack of evidence (BR-85),
        and the stored rows say the same thing rather than inventing one."""
        service, content = _service(
            [AnswerSentence(text="근거 없는 문장.", chunk_ids=[999])],
            [SupportVerdict.UNSUPPORTED],
        )

        service.answer("질문")

        assert len(_stored(content)) == 1
        assert _citations(content) == []


class TestThePartialAnswerPathStoresBothKinds:
    def test_the_removed_sentence_keeps_its_citation_alongside_the_kept_one(self):
        sentences = [
            AnswerSentence(text="살아남는 문장.", chunk_ids=[11]),
            AnswerSentence(text="걸러지는 문장.", chunk_ids=[11]),
        ]
        service, content = _service(
            sentences, [SupportVerdict.SUPPORTED, SupportVerdict.UNSUPPORTED]
        )

        result = service.answer("질문")

        assert result.outcome is AnswerOutcome.ANSWERED_PARTIAL
        kept_row, removed_row = _stored(content)
        assert removed_row.removed is True
        assert len(_by_sentence(content, kept_row)) == 1
        assert len(_by_sentence(content, removed_row)) == 1
        assert len(_snapshots(content)) == 2

    def test_what_the_user_is_handed_is_still_only_the_kept_sentence(self):
        """The stored rows grew; `QueryResult` must not. A citation for a
        sentence the user never sees, shown as if it supported the answer, is
        worse than storing nothing at all."""
        sentences = [
            AnswerSentence(text="살아남는 문장.", chunk_ids=[11]),
            AnswerSentence(text="걸러지는 문장.", chunk_ids=[11]),
        ]
        service, _content = _service(
            sentences, [SupportVerdict.SUPPORTED, SupportVerdict.UNSUPPORTED]
        )

        result = service.answer("질문")

        assert [s["text"] for s in result.sentences] == ["살아남는 문장."]
        assert [c["sentence_ordinal"] for c in result.citations] == [0]
        assert result.removed_count == 1

    def test_a_refusal_returns_no_citations_at_all(self):
        """Nothing survived, so nothing is shown — even though rows now exist."""
        service, content = _service(
            [AnswerSentence(text="문장.", chunk_ids=[11])], [SupportVerdict.UNSUPPORTED]
        )

        result = service.answer("질문")

        assert result.citations == []
        assert len(_citations(content)) == 1


class RecordingSession:
    """Captures the count statements `query_history` builds (NFR-28: no DB).

    The counts themselves are canned. What is being pinned is the predicate:
    the audit rows exist either way, and the screen must not be reading them.
    """

    def __init__(self, rows: list) -> None:
        self._rows = rows
        self.counts: list = []

    def scalars(self, _statement):
        return iter(self._rows)

    def scalar(self, statement):
        self.counts.append(statement)
        return 1


class _Row:
    def __init__(self) -> None:
        self.id = 7
        self.question = "암모니아가 눈에 닿으면?"
        self.outcome = AnswerOutcome.ANSWERED_PARTIAL.value
        self.owner_id = 3
        self.asked_at = None


def _history_statements() -> list:
    session = RecordingSession([_Row()])
    AccountService(session).query_history(AuthenticatedUser(id=3, email="a@b.test"))
    return session.counts


def _sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


class TestHistoryCountsOnlyWhatTheUserSaw:
    """FR-32's line reads "{n}문장 · 근거 {m}건". Both numbers describe an answer
    the user was given, so both exclude the rows kept for auditing."""

    def test_both_counts_exclude_removed_sentences(self):
        statements = _history_statements()

        assert len(statements) == 2
        for statement in statements:
            assert "answer_sentence.removed IS false" in _sql(statement)

    def test_the_counts_are_over_the_tables_they_claim_to_be(self):
        """Guards the test above from passing on a statement that filters
        `removed` and then counts the wrong thing."""
        sentences, citations = _history_statements()

        assert _sql(sentences).startswith("SELECT count(*)")
        assert "FROM answer_sentence" in _sql(sentences)
        assert "FROM answer_citation" in _sql(citations)

    def test_the_reference_statement_without_the_filter_would_not_pass(self):
        """The mutation this file exists to catch, written out: the query as it
        stood before C14 compiles without the predicate."""
        before = (
            select(func.count())
            .select_from(AnswerSentenceRow)
            .where(AnswerSentenceRow.query_id == 7)
        )

        assert "answer_sentence.removed" not in _sql(before)


class _Snapshot:
    """The columns `citations_for_answer` reads off `CitationSnapshotRow`."""

    def __init__(self) -> None:
        self.document_id = 1
        self.document_title = "산업안전보건법"
        self.section_code = "law_90"
        self.section_title = "제90조"
        self.snippet = "사업주는 물질안전보건자료를 게시하여야 한다."
        self.source_url = "https://example.test/law"


class _Rows:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def all(self) -> list[tuple]:
        return self._rows


class ReplayingSession:
    """Replays canned citation rows and keeps the statement (NFR-28: no DB).

    The rows stand in for what the join returns, so the tuple order is part of
    what is being pinned — a column added to the select in the wrong position
    unpacks into the wrong field here.
    """

    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows
        self.statements: list = []

    def execute(self, statement):
        self.statements.append(statement)
        return _Rows(self._rows)


def _citation_rows() -> list[tuple]:
    """Ordinal 0 survived, ordinal 1 was filtered — the partial-answer shape."""
    return [
        (0, 41, 0, 11, False, _Snapshot()),
        (1, 42, 0, 11, True, _Snapshot()),
    ]


class TestTheDetailViewSaysWhichCitationsWereFiltered:
    """`GET /api/query/{id}` hands `citations` straight out of here.

    C14 put the filtered sentences' citations in this list. That is right for
    an audit view and a trap for a consumer that renders the list as "the
    answer's sources", so the row carries the fact rather than being dropped:
    the audit reading stays complete and the display reading stays honest.
    """

    def test_the_citation_of_a_filtered_sentence_stays_in_the_list(self):
        """Filtering here would undo C11 and C14 one layer up. BR-88 again:
        rows kept for auditing are no use if the read path hides them."""
        session = ReplayingSession(_citation_rows())

        citations = citations_for_answer(session, 7)

        assert [c["sentence_ordinal"] for c in citations] == [0, 1]
        # The replay hands back whatever it is given, so the list above cannot
        # see a predicate. The predicate is what a future "just hide them"
        # would add, so the statement is checked directly.
        assert "answer_sentence.removed IS false" not in _sql(session.statements[0])

    def test_the_filtered_one_is_marked_and_the_surviving_one_is_not(self):
        """The whole point. Without the flag the two rows are indistinguishable
        without joining `sentences` on `sentence_ordinal`, and a consumer that
        does not join shows a dropped sentence's source as evidence."""
        session = ReplayingSession(_citation_rows())

        citations = citations_for_answer(session, 7)

        assert [c["removed"] for c in citations] == [False, True]

    def test_the_mark_is_read_from_the_sentence_row(self):
        """Guards the two above from passing on a hardcoded flag: the column
        has to be in the select, or the canned rows are just a fixture."""
        session = ReplayingSession([])

        citations_for_answer(session, 7)

        assert "answer_sentence.removed" in _sql(session.statements[0])

    def test_the_rest_of_the_citation_is_untouched(self):
        """C14 adds a field; it does not get to move BR-92a's snapshot read."""
        session = ReplayingSession(_citation_rows())

        first = citations_for_answer(session, 7)[0]

        assert first["citation_id"] == 41
        assert first["chunk_id"] == 11
        assert first["stale"] is False
        assert first["label"] == "law_90 제90조"
        assert first["snippet"] == _Snapshot().snippet
