"""ORM models E1~E12 (domain-entities.md).

Two things here are never populated by u1:
  * ``document.owner_id`` / ``chunk.owner_id``  -> u5 owner isolation
  * ``substance_synonym``                       -> u3 synonym lookup

They are pre-provisioned deliberately (DD-21, UD-6). Adding them later would
force an ALTER TABLE plus a full re-index over ~100k chunks.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.types import (
    DocType,
    ItemStatus,
    JobKind,
    JobStatus,
    PolicyDecision,
    StructureStatus,
)


class Base(DeclarativeBase):
    pass


class Source(Base):
    """E1 - a collectable data source and its policy state."""

    __tablename__ = "source"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # BR-02 / NFR-14 - the NAME of the env var, never the value.
    api_key_env: Mapped[str | None] = mapped_column(String(64))
    policy_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PolicyDecision.UNKNOWN.value
    )
    policy_reason: Mapped[str | None] = mapped_column(Text)
    policy_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    documents: Mapped[list[Document]] = relationship(back_populates="source")


class Substance(Base):
    """E2 - chemical substance master.

    GHS / H-P codes / physical properties are loaded in u1 but only *assembled*
    into a safety card in u3 (DD-10).
    """

    __tablename__ = "substance"
    __table_args__ = (
        CheckConstraint(
            "cas_number IS NOT NULL OR name_ko IS NOT NULL OR name_en IS NOT NULL",
            name="ck_substance_identifiable",
        ),
        Index("ix_substance_regulated", "is_regulated"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cas_number: Mapped[str | None] = mapped_column(String(20), unique=True)
    un_number: Mapped[str | None] = mapped_column(String(10))
    name_ko: Mapped[str | None] = mapped_column(String(300))
    name_en: Mapped[str | None] = mapped_column(String(300))
    ghs_classification: Mapped[dict | None] = mapped_column(JSONB)
    signal_word: Mapped[str | None] = mapped_column(String(20))
    h_codes: Mapped[list | None] = mapped_column(JSONB)
    p_codes: Mapped[list | None] = mapped_column(JSONB)
    physical_properties: Mapped[dict | None] = mapped_column(JSONB)
    is_regulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    synonyms: Mapped[list[SubstanceSynonym]] = relationship(
        back_populates="substance", cascade="all, delete-orphan"
    )


class SubstanceSynonym(Base):
    """E3 - pre-provisioned in u1, consumed by u3 (DD-21).

    Synonyms are captured at collection time. Introducing this table in u3 would
    mean re-collecting every substance record.
    """

    __tablename__ = "substance_synonym"
    __table_args__ = (
        UniqueConstraint("substance_id", "normalized_term", "term_type", name="uq_synonym_term"),
        Index("ix_synonym_normalized", "normalized_term"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    substance_id: Mapped[int] = mapped_column(
        ForeignKey("substance.id", ondelete="CASCADE"), nullable=False
    )
    term: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_term: Mapped[str] = mapped_column(String(300), nullable=False)
    term_type: Mapped[str] = mapped_column(String(32), nullable=False)

    substance: Mapped[Substance] = relationship(back_populates="synonyms")


class Document(Base):
    """E4 - one collected document.

    ``source_url`` and ``doc_type`` are NOT NULL by design: a document whose
    origin cannot be traced is never indexed (BR-32).
    """

    __tablename__ = "document"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_document_source_external"),
        Index("ix_document_hash", "content_hash"),
        Index("ix_document_doc_type", "doc_type"),
        Index("ix_document_owner", "owner_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source.id", ondelete="SET NULL"))
    external_id: Mapped[str | None] = mapped_column(String(200))
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    original_path: Mapped[str | None] = mapped_column(String(500))
    original_media_type: Mapped[str | None] = mapped_column(String(100))
    structure_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=StructureStatus.STRUCTURED.value
    )
    # u5 - NULL means public corpus. Never written in u1.
    owner_id: Mapped[int | None] = mapped_column(Integer)
    # u5 uploads. NULL for every collected document; the original filename lives
    # here and never in the stored path (NFR-13, BR-141).
    upload_filename: Mapped[str | None] = mapped_column(String(255))
    upload_size_bytes: Mapped[int | None] = mapped_column(Integer)
    upload_page_count: Mapped[int | None] = mapped_column(Integer)
    law_name: Mapped[str | None] = mapped_column(String(200))
    incident_occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    source: Mapped[Source | None] = relationship(back_populates="documents")
    extracted: Mapped[ExtractedTextRow | None] = relationship(
        back_populates="document", cascade="all, delete-orphan", uselist=False
    )
    sections: Mapped[list[DocumentSection]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[ChunkRow]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ExtractedTextRow(Base):
    """E5 - normalized text; the offset basis for the whole system (FQ-5=A)."""

    __tablename__ = "extracted_text"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    extractor: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="extracted")


class DocumentSection(Base):
    """E6 - no rows exist for documents marked ``unstructured`` (BR-24)."""

    __tablename__ = "document_section"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_section_ordinal"),
        Index("ix_section_code", "document_id", "section_code"),
        CheckConstraint("start_offset < end_offset", name="ck_section_offsets"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    section_code: Mapped[str | None] = mapped_column(String(50))
    section_title: Mapped[str | None] = mapped_column(String(300))
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)

    document: Mapped[Document] = relationship(back_populates="sections")


class ChunkRow(Base):
    """E7 - the retrieval unit."""

    __tablename__ = "chunk"
    __table_args__ = (
        Index("ix_chunk_document_ordinal", "document_id", "ordinal"),
        Index("ix_chunk_owner", "owner_id"),
        CheckConstraint("start_offset < end_offset", name="ck_chunk_offsets"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_section.id", ondelete="SET NULL")
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    # u5 - NULL means public. Never written in u1.
    owner_id: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
    embeddings: Mapped[list[ChunkEmbedding]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )


class ChunkEmbedding(Base):
    """E8 - kept out of ``chunk`` so a model swap can load new vectors alongside
    the old ones and cut over without downtime (BR-55, NFR-21)."""

    __tablename__ = "chunk_embedding"
    __table_args__ = (UniqueConstraint("chunk_id", "model_id", name="uq_embedding_chunk_model"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("chunk.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(get_settings().embedding_dim), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunk: Mapped[ChunkRow] = relationship(back_populates="embeddings")


class DocumentSubstance(Base):
    """E9 - many-to-many (FQ-6=A). A law document may link to zero substances;
    an incident report may mention several."""

    __tablename__ = "document_substance"

    document_id: Mapped[int] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), primary_key=True
    )
    substance_id: Mapped[int] = mapped_column(
        ForeignKey("substance.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(String(32), nullable=False)


class Job(Base):
    """E10 - job state lives here, never in the queue backend (DD-13)."""

    __tablename__ = "job"
    __table_args__ = (Index("ix_job_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=JobStatus.PENDING.value)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list[JobItem]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobItem(Base):
    """E11 - one document worth of work. ``last_stage`` is the resume point (BR-44)."""

    __tablename__ = "job_item"
    __table_args__ = (
        UniqueConstraint("job_id", "ref_key", name="uq_job_item_ref"),
        Index("ix_job_item_status", "job_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), nullable=False)
    ref_key: Mapped[str] = mapped_column(String(500), nullable=False)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("document.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ItemStatus.PENDING.value
    )
    last_stage: Mapped[str | None] = mapped_column(String(32))
    failure_kind: Mapped[str | None] = mapped_column(String(32))
    # BR-60 - masked before it is written.
    failure_reason: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    job: Mapped[Job] = relationship(back_populates="items")


class PolicyCheck(Base):
    """E12 - the audit trail proving blocked sources were NOT collected (CON-3)."""

    __tablename__ = "policy_check"
    __table_args__ = (Index("ix_policy_source_checked", "source_id", "checked_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source.id", ondelete="SET NULL"))
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorkerHeartbeat(Base):
    """Backs the worker health probe (BR-52)."""

    __tablename__ = "worker_heartbeat"

    worker_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    beat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class QueryLogRow(Base):
    """E14 - one row per question asked (FR-14, FQ2-20).

    Stateless by design (FR-22): there is no session or conversation id, because
    the system never consults history. The row exists for measurement (NFR-1,
    NFR-2), for honest refusal accounting (BR-78), and as the raw material for
    u4's golden set.
    """

    __tablename__ = "query_log"
    __table_args__ = (
        Index("ix_query_log_asked_at", "asked_at"),
        Index("ix_query_log_outcome", "outcome", "asked_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    asked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # u5 wires this up; until then every row is NULL (DD-21).
    owner_id: Mapped[int | None] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    refusal_reason: Mapped[str | None] = mapped_column(String(32))
    retrieval_ms: Mapped[int | None] = mapped_column(Integer)
    total_ms: Mapped[int | None] = mapped_column(Integer)
    candidate_count: Mapped[int | None] = mapped_column(Integer)
    top_score: Mapped[float | None] = mapped_column(Float)

    sentences: Mapped[list[AnswerSentenceRow]] = relationship(
        back_populates="query", cascade="all, delete-orphan"
    )


class AnswerSentenceRow(Base):
    """E15 - the answer is stored per sentence, not as one blob (FR-19).

    The sentence is the unit of both citation and grounding verification, so it
    is the unit of storage. A blob would make `removed` and `support`
    unrepresentable.
    """

    __tablename__ = "answer_sentence"
    __table_args__ = (UniqueConstraint("query_id", "ordinal", name="uq_answer_sentence"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    query_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("query_log.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    support: Mapped[str] = mapped_column(String(16), nullable=False)
    removed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    query: Mapped[QueryLogRow] = relationship(back_populates="sentences")
    citations: Mapped[list[AnswerCitationRow]] = relationship(
        back_populates="sentence", cascade="all, delete-orphan"
    )


class AnswerCitationRow(Base):
    """E16 - sentence <-> chunk.

    ``chunk_id`` is nullable with ON DELETE SET NULL, and that is the whole
    design decision. Re-indexing replaces chunks wholesale (BR-54): CASCADE
    would delete past citations silently, and RESTRICT would refuse the delete
    entirely - making any document that was ever cited permanently
    un-reindexable. Re-indexing is not a corner case here; it is how BR-20a,
    BR-31a and BR-27a were all shipped without re-fetching a single source.

    So the link is optional and the *snapshot* is authoritative. NULL does not
    mean "evidence lost", it means "this chunk has since been re-indexed".
    Display never joins `chunk` (BR-92a).
    """

    __tablename__ = "answer_citation"
    __table_args__ = (
        UniqueConstraint("sentence_id", "chunk_id", name="uq_answer_citation"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sentence_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("answer_sentence.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("chunk.id", ondelete="SET NULL")
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    sentence: Mapped[AnswerSentenceRow] = relationship(back_populates="citations")
    snapshot: Mapped[CitationSnapshotRow | None] = relationship(
        back_populates="citation", cascade="all, delete-orphan", uselist=False
    )


class CitationSnapshotRow(Base):
    """E17 - what the citation pointed at, frozen at answer time (BR-92).

    Written inside the same transaction as the sentence and the citation. A
    citation without a snapshot must not exist: display reads only this table
    (BR-92a), so such a row could show nothing, and once re-indexing has passed
    over it there is no way to recover what it meant.

    Immutable. Later revisions of the source do not rewrite it - the point is to
    preserve what the answer actually relied on.
    """

    __tablename__ = "citation_snapshot"

    citation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("answer_citation.id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    document_title: Mapped[str | None] = mapped_column(Text)
    # NULL is expected, not exceptional: BR-20a demotions and BR-31a merged
    # records genuinely have no section label (BR-90 renders it as such).
    section_code: Mapped[str | None] = mapped_column(String(64))
    section_title: Mapped[str | None] = mapped_column(String(200))
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)

    citation: Mapped[AnswerCitationRow] = relationship(back_populates="snapshot")


class LlmCallRow(Base):
    """E18 - one row per LLM call (FR-41, NFR-19).

    u1's `TraceRepo` was in-memory; this is where it becomes a real table.
    Failed calls are recorded too (BR-95) - a usage view that only counts
    successes understates what was actually spent.
    """

    __tablename__ = "llm_call"
    __table_args__ = (
        Index("ix_llm_call_called_at", "called_at"),
        Index("ix_llm_call_purpose", "purpose", "called_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    query_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("query_log.id", ondelete="SET NULL")
    )
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_name: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL, never 0, when the model has no registered price (BR-96). Zero would
    # make the usage screen report "free", which is a lie rather than a gap.
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    stop_reason: Mapped[str | None] = mapped_column(String(32))
    error_kind: Mapped[str | None] = mapped_column(String(32))


class EvaluationRun(Base):
    """E19 - one evaluation execution (FR-39).

    Records far more than `metrics` on purpose. A run whose numbers moved is
    useless unless you can tell **what** moved: the model, the prompt, the
    corpus, or the code. u2 defect 34 came from reasoning about a budget without
    the measurement that belonged to it; keeping only the aggregate would put
    every future regression in the same position.
    """

    __tablename__ = "evaluation_run"
    __table_args__ = (
        Index("ix_eval_run_baseline", "is_baseline", "finished_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    golden_set_path: Mapped[str] = mapped_column(String(512), nullable=False)
    golden_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    answer_model: Mapped[str | None] = mapped_column(String(128))
    judge_model: Mapped[str | None] = mapped_column(String(128))
    prompt_versions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    corpus_fingerprint: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Which code produced these numbers (defect 58). Nullable because runs
    # 1-153 predate the column and NULL is the honest answer for them.
    build_id: Mapped[str | None] = mapped_column(String(64))
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    baseline_id: Mapped[int | None] = mapped_column(
        ForeignKey("evaluation_run.id", ondelete="SET NULL")
    )
    # BR-129 - a person promotes a baseline. Never automatic: an automatic
    # promotion makes a worse run the new reference and the regression is then
    # invisible forever.
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[EvaluationItem]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class EvaluationItem(Base):
    """E20 - one golden question, scored (FR-37, FR-38).

    One row, one transaction (BR-117). A full run takes days on the free tier -
    measured, 25 answerable questions cost 131 LLM calls against a 20/day cap -
    so it *will* be interrupted, and a run that cannot be resumed cannot finish.
    """

    __tablename__ = "evaluation_item"
    __table_args__ = (
        UniqueConstraint("run_id", "question_id", name="uq_eval_item_question"),
        Index("ix_eval_item_run_status", "run_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_run.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    expects: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    # SET NULL for the same reason as `answer_citation.chunk_id` (BR-93): an
    # evaluation result has to outlive the query log it came from. Six months on,
    # the Recall figure still means something after the logs are pruned.
    query_id: Mapped[int | None] = mapped_column(
        ForeignKey("query_log.id", ondelete="SET NULL")
    )
    outcome: Mapped[str | None] = mapped_column(String(32))
    # The ordered candidate list, kept so metric code can be re-run for free
    # (BR-121). Changing k in Recall@k must not cost a day of quota.
    retrieved: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    recall_at_5: Mapped[float | None] = mapped_column(Numeric(4, 3))
    recall_at_10: Mapped[float | None] = mapped_column(Numeric(4, 3))
    reciprocal_rank: Mapped[float | None] = mapped_column(Numeric(4, 3))
    citation_precision: Mapped[float | None] = mapped_column(Numeric(4, 3))
    refusal_correct: Mapped[bool | None] = mapped_column(Boolean)
    judge_correct: Mapped[bool | None] = mapped_column(Boolean)
    judge_faithful: Mapped[bool | None] = mapped_column(Boolean)
    # The judge is a model too. Storing only its verdict leaves nothing to read
    # when the number moves.
    judge_reason: Mapped[str | None] = mapped_column(Text)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_ms: Mapped[int | None] = mapped_column(Integer)
    error_kind: Mapped[str | None] = mapped_column(String(64))
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run: Mapped[EvaluationRun] = relationship(back_populates="items")


class UserAccount(Base):
    """E21 - an account (FR-31~33).

    `owner_id` on `document`, `chunk` and `query_log` refers to this id. There
    is deliberately **no foreign key**: those columns predate this table by four
    units, and adding the constraint now would force a policy for what happens
    to a user's documents when the account is deleted - a feature that does not
    exist. Absent features do not get cascade rules.
    """

    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stored lower-cased (BR-132). Case-sensitive uniqueness would let one
    # person hold two accounts, and the moment that happens their uploads are
    # invisible from the other one - which reads as an isolation bug and is not.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # FR-34's other half. u2 shipped the always-visible disclaimer (FR-35); the
    # record of consent needed an account and so waited for this unit.
    disclaimer_version: Mapped[str] = mapped_column(String(16), nullable=False)
    disclaimer_agreed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # AP-2 - a delay, not a lockout. Reset to zero on success.
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Enum classes are imported for documentation of the allowed column values.
# Columns store short strings so that psql output stays readable and migrations
# do not need native enum types (see domain-entities.md section 2).
__all__ = [
    "AnswerCitationRow",
    "AnswerSentenceRow",
    "Base",
    "ChunkEmbedding",
    "ChunkRow",
    "CitationSnapshotRow",
    "DocType",
    "Document",
    "DocumentSection",
    "DocumentSubstance",
    "EvaluationItem",
    "EvaluationRun",
    "ExtractedTextRow",
    "ItemStatus",
    "Job",
    "JobItem",
    "JobKind",
    "JobStatus",
    "LlmCallRow",
    "PolicyCheck",
    "PolicyDecision",
    "QueryLogRow",
    "Source",
    "StructureStatus",
    "Substance",
    "SubstanceSynonym",
    "UserAccount",
    "WorkerHeartbeat",
]
