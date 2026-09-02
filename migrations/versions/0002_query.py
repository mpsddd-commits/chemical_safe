"""u2 query schema - entities E14~E18.

No u1 table is altered. That is not a coincidence: `answer_citation.chunk_id`
uses ON DELETE SET NULL precisely so re-indexing (BR-54) keeps working untouched.
RESTRICT would have made any document that was ever cited permanently
un-reindexable, and re-indexing is how every parsing-rule change ships here
(BR-20a, BR-31a, BR-27a all went out that way, without re-fetching a source).

Revision ID: 0002_query
Revises: 0001_base
Create Date: 2026-08-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_query"
down_revision = "0001_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- E14 query_log ----
    op.create_table(
        "query_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "asked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # u5 owner isolation. Always NULL until then (DD-21).
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("refusal_reason", sa.String(32), nullable=True),
        sa.Column("retrieval_ms", sa.Integer(), nullable=True),
        sa.Column("total_ms", sa.Integer(), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=True),
        sa.Column("top_score", sa.Float(), nullable=True),
    )
    op.create_index("ix_query_log_asked_at", "query_log", [sa.text("asked_at DESC")])
    op.create_index(
        "ix_query_log_outcome", "query_log", ["outcome", sa.text("asked_at DESC")]
    )

    # ---- E15 answer_sentence ----
    op.create_table(
        "answer_sentence",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "query_id",
            sa.BigInteger(),
            sa.ForeignKey("query_log.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("support", sa.String(16), nullable=False),
        sa.Column("removed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("query_id", "ordinal", name="uq_answer_sentence"),
    )

    # ---- E16 answer_citation ----
    op.create_table(
        "answer_citation",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "sentence_id",
            sa.BigInteger(),
            sa.ForeignKey("answer_sentence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Nullable + SET NULL. See module docstring; NULL means "re-indexed",
        # not "evidence lost" - the snapshot below is what display reads.
        sa.Column(
            "chunk_id",
            sa.BigInteger(),
            sa.ForeignKey("chunk.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        # PostgreSQL treats NULLs as distinct here, so one sentence may hold
        # several NULL citations after a re-index. That is intended: each row
        # carries its own snapshot and they are different pieces of evidence.
        sa.UniqueConstraint("sentence_id", "chunk_id", name="uq_answer_citation"),
    )

    # ---- E17 citation_snapshot ----
    op.create_table(
        "citation_snapshot",
        sa.Column(
            "citation_id",
            sa.BigInteger(),
            sa.ForeignKey("answer_citation.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("document_id", sa.Integer(), nullable=False),
        # NOT NULL: BR-32 guarantees every document has one, and a citation the
        # reader cannot follow back to a source is not a citation.
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("document_title", sa.Text(), nullable=True),
        # NULL is normal here - BR-20a demotions and BR-31a merged records have
        # no section label, and inventing one would be worse (BR-90).
        sa.Column("section_code", sa.String(64), nullable=True),
        sa.Column("section_title", sa.String(200), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
    )

    # ---- E18 llm_call ----
    op.create_table(
        "llm_call",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "query_id",
            sa.BigInteger(),
            sa.ForeignKey("query_log.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "called_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_name", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        # Nullable, never defaulted to 0 (BR-96): an unpriced model must read as
        # "unknown" on the usage screen, not as "free".
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("stop_reason", sa.String(32), nullable=True),
        sa.Column("error_kind", sa.String(32), nullable=True),
    )
    op.create_index("ix_llm_call_called_at", "llm_call", [sa.text("called_at DESC")])
    op.create_index(
        "ix_llm_call_purpose", "llm_call", ["purpose", sa.text("called_at DESC")]
    )


def downgrade() -> None:
    op.drop_table("llm_call")
    op.drop_table("citation_snapshot")
    op.drop_table("answer_citation")
    op.drop_table("answer_sentence")
    op.drop_table("query_log")
