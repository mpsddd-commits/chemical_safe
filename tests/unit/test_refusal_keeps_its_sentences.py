"""A refusal must leave behind what it refused — BR-88 on the refusal path.

Measured 2026-09-08. Run 609 refused three questions and the `answer_sentence`
table held **zero** rows for all three (`query_log` 448, 450, 462), while the
screen and `QueryResult` both reported a `removed_count`. The BR-88 comment in
`query_service` already says why that is not allowed — "a count with no rows
behind it cannot be audited" — and the branch that refuses was the one breaking
it.

The cost was not theoretical. msds-03 and sub-04 refused in run 609 and answered
in all three reproductions five minutes later, same code, same corpus,
temperature 0. Nothing about that is diagnosable without the generated sentences
and the verdicts they were given, and the refusal had erased both.

These tests pin the two halves that matter: the rows now exist with each
sentence's own verdict, and nothing the user sees changed while they appeared.
"""

from __future__ import annotations

import pytest

from app.core.types import (
    AnswerOutcome,
    DocType,
    RefusalReason,
    RetrievalMode,
    SupportVerdict,
)
from app.db.models import AnswerSentenceRow
from app.rag.types import AnswerSentence, Evidence
from app.rag.verifier import VerifiedSentence
from app.services.query_service import QueryService


class FakeSession:
    """Records what was added. No database — see the integration suite for that."""

    def __init__(self) -> None:
        self.added: list = []
        self.commits = 0
        self._next_id = 1

    def add(self, obj) -> None:
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = self._next_id
            self._next_id += 1

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass


class FakeGenerator:
    def __init__(self, sentences: list[AnswerSentence]) -> None:
        self._sentences = sentences

    def generate(self, question, evidence, on_delta=None):
        from app.rag.generator import GenerationOutcome

        return GenerationOutcome(sentences=self._sentences)


class FakeVerifier:
    """Hands back the verdicts the test asked for, in order."""

    def __init__(self, verdicts: list[SupportVerdict]) -> None:
        self._verdicts = verdicts

    def verify_all(self, sentences, evidence_by_id):
        return [
            VerifiedSentence(sentence, verdict)
            for sentence, verdict in zip(sentences, self._verdicts, strict=True)
        ]


def _evidence(chunk_id: int = 11) -> Evidence:
    """Strong enough to pass stage one, so the test reaches verification.

    `law` on purpose: an MSDS or substance chunk with no named subject is
    refused by BR-73a before any generation happens.
    """
    return Evidence(
        chunk_id=chunk_id,
        document_id=1,
        source_url="https://example.test/law",
        document_title="산업안전보건법",
        section_code="law_90",
        section_title="제90조",
        text="사업주는 물질안전보건자료를 게시하여야 한다.",
        start_offset=0,
        end_offset=30,
        score=0.9,
        doc_type=DocType.LAW,
        relevance=0.9,
    )


def _service(sentences: list[AnswerSentence], verdicts: list[SupportVerdict]):
    content, log = FakeSession(), FakeSession()
    service = QueryService(content, llm=object(), embedder=object(), obs_session=log)
    evidence = [_evidence()]
    service.retrieve = lambda _q, _s: (evidence, evidence, RetrievalMode.HYBRID)
    service._generator = FakeGenerator(sentences)
    service._verifier = FakeVerifier(verdicts)
    return service, content


def _stored(content: FakeSession) -> list[AnswerSentenceRow]:
    return [row for row in content.added if isinstance(row, AnswerSentenceRow)]


class TestRefusalStoresWhatItFiltered:
    def test_all_unsupported_refuses_and_still_stores_the_sentences(self):
        """The rows run 609 did not have."""
        sentences = [
            AnswerSentence(text="황산은 중화 후 폐기한다.", chunk_ids=[11]),
            AnswerSentence(text="보호장갑을 착용한다.", chunk_ids=[11]),
        ]
        service, content = _service(
            sentences, [SupportVerdict.UNSUPPORTED, SupportVerdict.UNSUPPORTED]
        )

        result = service.answer("황산은 어떻게 폐기하나요?")

        assert result.outcome is AnswerOutcome.REFUSED_UNSUPPORTED
        rows = _stored(content)
        assert [r.text for r in rows] == [s.text for s in sentences]
        assert all(r.removed is True for r in rows)
        assert [r.ordinal for r in rows] == [0, 1]

    def test_each_sentence_keeps_its_own_verdict(self):
        """"We judged it and it failed" and "we never got to ask" are different
        facts (BR-87), and a single stored value for both would have hidden the
        quota-exhausted case behind a rejection."""
        sentences = [
            AnswerSentence(text="첫 문장.", chunk_ids=[11]),
            AnswerSentence(text="둘째 문장.", chunk_ids=[11]),
        ]
        service, content = _service(
            sentences, [SupportVerdict.UNSUPPORTED, SupportVerdict.UNVERIFIED]
        )

        service.answer("질문")

        assert [r.support for r in _stored(content)] == [
            SupportVerdict.UNSUPPORTED.value,
            SupportVerdict.UNVERIFIED.value,
        ]

    def test_what_the_user_sees_is_unchanged(self):
        """This change adds observation. If any of these move it stopped being
        observation and became a behaviour change."""
        sentences = [AnswerSentence(text="문장.", chunk_ids=[11])]
        service, _content = _service(sentences, [SupportVerdict.UNSUPPORTED])

        result = service.answer("질문")

        assert result.outcome is AnswerOutcome.REFUSED_UNSUPPORTED
        assert result.refusal_reason is RefusalReason.ALL_SENTENCES_UNSUPPORTED
        assert result.sentences == []
        assert result.citations == []
        assert result.removed_count == 1
        assert [link["document_id"] for link in result.links] == [1]

    def test_a_kept_sentence_is_not_this_path(self):
        """Guards the test above from passing for the wrong reason."""
        sentences = [AnswerSentence(text="문장.", chunk_ids=[11])]
        service, _content = _service(sentences, [SupportVerdict.SUPPORTED])

        result = service.answer("질문")

        assert result.outcome is AnswerOutcome.ANSWERED


class TestEmptyGenerationIsDistinguishable:
    """Zero sentences and all-sentences-filtered share one `RefusalReason`.

    Widening the enum would reach the screen text, the repository's outcome
    mapping and the evaluation verdicts, and baseline 609 was promoted against
    the reasons as they stand. So the two are separated in the log instead —
    which is enough to tell them apart when reading back a refusal.
    """

    def test_no_generated_sentences_logs_empty_generation(self, caplog):
        service, content = _service([], [])

        with caplog.at_level("WARNING"):
            result = service.answer("질문")

        assert result.refusal_reason is RefusalReason.ALL_SENTENCES_UNSUPPORTED
        assert _stored(content) == []
        assert any(r.message == "empty_generation" for r in caplog.records)

    def test_filtered_sentences_do_not_log_empty_generation(self):
        service, _content = _service(
            [AnswerSentence(text="문장.", chunk_ids=[11])],
            [SupportVerdict.UNSUPPORTED],
        )

        import logging

        records: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = records.append  # type: ignore[method-assign]
        logger = logging.getLogger("app.services.query_service")
        logger.addHandler(handler)
        try:
            service.answer("질문")
        finally:
            logger.removeHandler(handler)

        assert not [r for r in records if r.message == "empty_generation"]


@pytest.mark.parametrize(
    "verdicts,expected",
    [
        ([SupportVerdict.UNSUPPORTED], 1),
        ([SupportVerdict.UNVERIFIED, SupportVerdict.UNSUPPORTED], 2),
    ],
)
def test_removed_count_has_rows_behind_it(verdicts, expected):
    """BR-88 stated as the invariant it is: the number on the screen and the
    number of rows in the table are the same number."""
    sentences = [
        AnswerSentence(text=f"문장 {i}.", chunk_ids=[11]) for i in range(len(verdicts))
    ]
    service, content = _service(sentences, verdicts)

    result = service.answer("질문")

    assert result.removed_count == expected
    assert len(_stored(content)) == expected
