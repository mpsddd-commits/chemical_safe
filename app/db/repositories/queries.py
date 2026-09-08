"""QueryRepo - persistence for E14~E17 (W8 step 7).

Two sessions, because two different things are being written and they must not
share a fate.

**Answer content** (E15 sentences, E16 citations, E17 snapshots) goes to the
content session and commits together or not at all (BR-92). A citation without
its snapshot is unusable - display reads only the snapshot (BR-92a), and once a
re-index has passed there is no recovering what it pointed at.

**The record that a query ran** (E14, and E18 alongside it) goes to the log
session and commits on its own. Measured 2026-08-25: with one shared session, a
failed query rolled back its own `query_log` row and every `llm_call` row with
it - observability vanished exactly when it was wanted, and BR-78 ("a refusal is
recorded, not an error") and BR-95 ("failed calls are recorded too") could not
hold on the error path.

That asymmetry is the design, not an oversight: an answer whose evidence cannot
be shown must not exist, but the *fact* that we tried must survive anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.types import AnswerOutcome, RefusalReason, RetrievalMode, SupportVerdict
from app.db.models import (
    AnswerCitationRow,
    AnswerSentenceRow,
    CitationSnapshotRow,
    QueryLogRow,
)


@dataclass
class CitationDraft:
    """One citation plus the snapshot that must land with it."""

    chunk_id: int
    rank: int
    document_id: int
    source_url: str
    document_title: str | None
    section_code: str | None
    section_title: str | None
    snippet: str
    start_offset: int
    end_offset: int


@dataclass
class SentenceDraft:
    ordinal: int
    text: str
    support: SupportVerdict
    removed: bool
    citations: list[CitationDraft]


class QueryRepo:
    def __init__(self, session: Session, log_session: Session | None = None) -> None:
        self._s = session
        # Defaults to the content session so unit tests and read-only callers
        # need not care. The app hands in a separate one.
        self._log = log_session if log_session is not None else session

    def commit_log(self) -> None:
        """Make the observability facts durable, independently of the answer.

        The only place transaction control appears in a repository, and it is
        here on purpose: the whole reason for the second session is that these
        rows must outlive a failure of the work they describe.
        """
        if self._log is self._s:
            # Sharing a session (tests): committing here would commit the
            # answer content early and defeat BR-92.
            return
        try:
            self._log.commit()
        except Exception:  # noqa: BLE001 - never mask the real failure
            self._log.rollback()

    def start(self, question: str, mode: RetrievalMode) -> QueryLogRow:
        """Open the log row before retrieval so timings have somewhere to land."""
        row = QueryLogRow(
            question=question,
            mode=mode.value,
            # Overwritten on every terminal path. `error` is the right default
            # because an unfinished query is a failed one, not a successful one.
            outcome=AnswerOutcome.ERROR.value,
        )
        self._log.add(row)
        self._log.flush()
        return row

    def record_retrieval(
        self, row: QueryLogRow, *, candidate_count: int, top_score: float | None, ms: int
    ) -> None:
        row.candidate_count = candidate_count
        row.top_score = top_score
        row.retrieval_ms = ms

    def refuse(
        self,
        row: QueryLogRow,
        reason: RefusalReason,
        *,
        total_ms: int,
        sentences: list[SentenceDraft] | None = None,
    ) -> None:
        """BR-78 - refusal is an outcome, not a failure.

        `sentences` carries whatever verification filtered out, and it exists
        because the refusal path was breaking BR-88 on its own. `finalise`
        already stores removed sentences with the reason a count with no rows
        behind it cannot be audited; a refusal reports `removed_count` too and
        stored nothing at all. Measured 2026-09-08: run 609's three refusals
        (`query_log` 448, 450, 462) each had **zero** `answer_sentence` rows, so
        when msds-03 and sub-04 refused in 609 and then answered in all three
        reproductions five minutes later at temperature 0, there was nothing to
        read - not the generated text, not the verdicts. A refusal that erases
        its own evidence cannot be diagnosed.

        Rows land on the content session, exactly as `finalise` puts them there,
        so the refusal's sentences share the fate of an answer's sentences
        (BR-92) rather than getting a second, weaker rule of their own. The
        stage-one refusals pass nothing: no generation happened, so there is
        nothing to store.
        """
        row.outcome = (
            AnswerOutcome.REFUSED_UNSUPPORTED.value
            if reason is RefusalReason.ALL_SENTENCES_UNSUPPORTED
            else AnswerOutcome.REFUSED_LOW_RELEVANCE.value
        )
        row.refusal_reason = reason.value
        row.total_ms = total_ms
        self._write_sentences(row, sentences or [])

    def mark_error(self, row: QueryLogRow, *, total_ms: int) -> None:
        """The query did not finish. Recorded, not silently lost.

        `outcome` already defaults to `error` at `start`; this fixes the timing
        so the row is usable for diagnosis rather than merely present.
        """
        row.outcome = AnswerOutcome.ERROR.value
        row.total_ms = total_ms

    def finalise(
        self,
        row: QueryLogRow,
        sentences: list[SentenceDraft],
        *,
        outcome: AnswerOutcome,
        total_ms: int,
    ) -> None:
        """BR-92 - sentences, citations and snapshots in one transaction.

        The caller's `session_scope` owns the commit. Raising here rolls back the
        whole answer, which is the intended behaviour: see the module docstring.
        """
        row.outcome = outcome.value
        row.total_ms = total_ms
        self._write_sentences(row, sentences)

    def _write_sentences(
        self, row: QueryLogRow, sentences: list[SentenceDraft]
    ) -> None:
        """E15~E17 on the *content* session: this is the BR-92 unit.

        Shared by `finalise` and `refuse` so an answer's sentences and a
        refusal's sentences are written by the same code. Two copies would drift,
        and the drift that matters here is silent - a refusal storing rows in a
        subtly different shape reads as a corpus fact rather than as a bug.
        """
        for draft in sentences:
            sentence = AnswerSentenceRow(
                query_id=row.id,
                ordinal=draft.ordinal,
                text=draft.text,
                support=draft.support.value,
                removed=draft.removed,
            )
            self._s.add(sentence)
            self._s.flush()

            for cite in draft.citations:
                citation = AnswerCitationRow(
                    sentence_id=sentence.id, chunk_id=cite.chunk_id, rank=cite.rank
                )
                self._s.add(citation)
                self._s.flush()
                # Frozen now, not at re-index time: by then the source may
                # already have changed underneath us.
                self._s.add(
                    CitationSnapshotRow(
                        citation_id=citation.id,
                        document_id=cite.document_id,
                        source_url=cite.source_url,
                        document_title=cite.document_title,
                        section_code=cite.section_code,
                        section_title=cite.section_title,
                        snippet=cite.snippet,
                        start_offset=cite.start_offset,
                        end_offset=cite.end_offset,
                    )
                )

    # ---- read paths (BR-92a: snapshot only, never `chunk`) ----

    def get(self, query_id: int) -> QueryLogRow | None:
        return self._s.get(QueryLogRow, query_id)

    def snapshot_for_citation(self, citation_id: int) -> CitationSnapshotRow | None:
        return self._s.get(CitationSnapshotRow, citation_id)

    def sentences_for(self, query_id: int) -> list[AnswerSentenceRow]:
        stmt = (
            select(AnswerSentenceRow)
            .where(AnswerSentenceRow.query_id == query_id)
            .order_by(AnswerSentenceRow.ordinal)
        )
        return list(self._s.scalars(stmt))

    def purge_expired(self, retention_days: int) -> int:
        """FQ3-16 / NFR-14 - questions may be personal; they do not live forever.

        Cascades remove the sentences, citations and snapshots with the log row.
        """
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        result = self._s.execute(
            delete(QueryLogRow).where(QueryLogRow.asked_at < cutoff)
        )
        return result.rowcount or 0
