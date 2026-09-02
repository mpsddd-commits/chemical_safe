"""u1 base schema - entities E1~E12 plus the worker heartbeat.

Two things in this revision are not used by u1 and that is deliberate (UD-6,
DD-21):

  * ``document.owner_id`` / ``chunk.owner_id`` - u5 owner isolation
  * ``substance_synonym``                      - u3 synonym lookup

Adding either later would mean an ALTER TABLE over ~100k chunk rows plus a full
re-index, or re-collecting every substance record. Both are cheap now and
expensive later, so they land here.

Revision ID: 0001_base
Revises:
Create Date: 2026-08-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings

revision = "0001_base"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = get_settings().embedding_dim


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ---- E1 source ----
    op.create_table(
        "source",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("requires_api_key", sa.Boolean, nullable=False, server_default=sa.false()),
        # NFR-14: the NAME of the env var only.
        sa.Column("api_key_env", sa.String(64)),
        sa.Column("policy_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("policy_reason", sa.Text),
        sa.Column("policy_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_collected_at", sa.DateTime(timezone=True)),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
    )

    # ---- E2 substance ----
    op.create_table(
        "substance",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cas_number", sa.String(20), unique=True),
        sa.Column("un_number", sa.String(10)),
        sa.Column("name_ko", sa.String(300)),
        sa.Column("name_en", sa.String(300)),
        sa.Column("ghs_classification", postgresql.JSONB),
        sa.Column("signal_word", sa.String(20)),
        sa.Column("h_codes", postgresql.JSONB),
        sa.Column("p_codes", postgresql.JSONB),
        sa.Column("physical_properties", postgresql.JSONB),
        sa.Column("is_regulated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        # BR-33 - a substance must be identifiable by something.
        sa.CheckConstraint(
            "cas_number IS NOT NULL OR name_ko IS NOT NULL OR name_en IS NOT NULL",
            name="ck_substance_identifiable",
        ),
    )
    op.create_index("ix_substance_regulated", "substance", ["is_regulated"])

    # ---- E3 substance_synonym (pre-provisioned for u3) ----
    op.create_table(
        "substance_synonym",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("substance_id", sa.Integer,
                  sa.ForeignKey("substance.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term", sa.String(300), nullable=False),
        sa.Column("normalized_term", sa.String(300), nullable=False),
        sa.Column("term_type", sa.String(32), nullable=False),
        sa.UniqueConstraint("substance_id", "normalized_term", "term_type",
                            name="uq_synonym_term"),
    )
    op.create_index("ix_synonym_normalized", "substance_synonym", ["normalized_term"])

    # ---- E4 document ----
    op.create_table(
        "document",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("source.id", ondelete="SET NULL")),
        sa.Column("external_id", sa.String(200)),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(500)),
        # BR-32 - no traceable origin means no row at all.
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("revised_at", sa.DateTime(timezone=True)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("original_path", sa.String(500)),
        sa.Column("original_media_type", sa.String(100)),
        sa.Column("structure_status", sa.String(32), nullable=False,
                  server_default="structured"),
        # u5 - NULL means public corpus.
        sa.Column("owner_id", sa.Integer),
        sa.Column("law_name", sa.String(200)),
        sa.Column("incident_occurred_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("source_id", "external_id", name="uq_document_source_external"),
    )
    op.create_index("ix_document_hash", "document", ["content_hash"])
    op.create_index("ix_document_doc_type", "document", ["doc_type"])
    op.create_index("ix_document_owner", "document", ["owner_id"])

    # ---- E5 extracted_text ----
    op.create_table(
        "extracted_text",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer,
                  sa.ForeignKey("document.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("char_count", sa.Integer, nullable=False),
        sa.Column("extractor", sa.String(64), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )

    # ---- E6 document_section ----
    op.create_table(
        "document_section",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer,
                  sa.ForeignKey("document.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("section_code", sa.String(50)),
        sa.Column("section_title", sa.String(300)),
        sa.Column("start_offset", sa.Integer, nullable=False),
        sa.Column("end_offset", sa.Integer, nullable=False),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_section_ordinal"),
        sa.CheckConstraint("start_offset < end_offset", name="ck_section_offsets"),
    )
    op.create_index("ix_section_code", "document_section", ["document_id", "section_code"])

    # ---- E7 chunk ----
    op.create_table(
        "chunk",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("document_id", sa.Integer,
                  sa.ForeignKey("document.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", sa.Integer,
                  sa.ForeignKey("document_section.id", ondelete="SET NULL")),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("start_offset", sa.Integer, nullable=False),
        sa.Column("end_offset", sa.Integer, nullable=False),
        # u5 - NULL means public.
        sa.Column("owner_id", sa.Integer),
        sa.Column("meta", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.CheckConstraint("start_offset < end_offset", name="ck_chunk_offsets"),
    )
    op.create_index("ix_chunk_document_ordinal", "chunk", ["document_id", "ordinal"])
    op.create_index("ix_chunk_owner", "chunk", ["owner_id"])

    # FR-12 - CAS / UN / substance name must match exactly. A generic text search
    # configuration would split "7664-93-9" into fragments, so these are indexed
    # as plain expression btrees alongside the full text index (BR-38).
    op.execute(
        "CREATE INDEX ix_chunk_meta_cas ON chunk ((meta->>'cas_number'))"
    )
    op.execute(
        "CREATE INDEX ix_chunk_meta_un ON chunk ((meta->>'un_number'))"
    )
    op.execute(
        "CREATE INDEX ix_chunk_meta_doc_type ON chunk ((meta->>'doc_type'))"
    )
    op.execute(
        "CREATE INDEX ix_chunk_fts ON chunk USING GIN (to_tsvector('simple', text))"
    )

    # ---- E8 chunk_embedding ----
    op.create_table(
        "chunk_embedding",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("chunk_id", sa.BigInteger,
                  sa.ForeignKey("chunk.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(128), nullable=False),
        sa.Column("dim", sa.Integer, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("chunk_id", "model_id", name="uq_embedding_chunk_model"),
    )
    # HNSW is created empty; it stays valid as rows arrive.
    op.execute(
        "CREATE INDEX ix_chunk_embedding_hnsw ON chunk_embedding "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # ---- E9 document_substance ----
    op.create_table(
        "document_substance",
        sa.Column("document_id", sa.Integer,
                  sa.ForeignKey("document.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("substance_id", sa.Integer,
                  sa.ForeignKey("substance.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("relation", sa.String(32), nullable=False),
    )
    op.create_index("ix_document_substance_substance", "document_substance", ["substance_id"])

    # ---- E10 job ----
    op.create_table(
        "job",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("params", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("total_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )
    op.create_index("ix_job_status_created", "job", ["status", "created_at"])

    # ---- E11 job_item ----
    op.create_table(
        "job_item",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("job.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("ref_key", sa.String(500), nullable=False),
        sa.Column("document_id", sa.Integer,
                  sa.ForeignKey("document.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        # BR-44 - the resume point.
        sa.Column("last_stage", sa.String(32)),
        sa.Column("failure_kind", sa.String(32)),
        # BR-60 - masked before write.
        sa.Column("failure_reason", sa.Text),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("job_id", "ref_key", name="uq_job_item_ref"),
    )
    op.create_index("ix_job_item_status", "job_item", ["job_id", "status"])

    # ---- E12 policy_check ----
    op.create_table(
        "policy_check",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("source.id", ondelete="SET NULL")),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )
    op.create_index("ix_policy_source_checked", "policy_check", ["source_id", "checked_at"])

    # ---- worker heartbeat (BR-52) ----
    op.create_table(
        "worker_heartbeat",
        sa.Column("worker_id", sa.String(64), primary_key=True),
        sa.Column("beat_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeat")
    op.drop_table("policy_check")
    op.drop_table("job_item")
    op.drop_table("job")
    op.drop_table("document_substance")
    op.drop_table("chunk_embedding")
    op.drop_table("chunk")
    op.drop_table("document_section")
    op.drop_table("extracted_text")
    op.drop_table("document")
    op.drop_table("substance_synonym")
    op.drop_table("substance")
    op.drop_table("source")
