"""u4 evaluation schema - entities E19, E20.

Two new tables and **not one alteration** to anything u1/u2/u3 built. That is
the point: evaluation observes the system, so it must not be able to change it.

`evaluation_item.query_id` is ON DELETE SET NULL for the same reason
`answer_citation.chunk_id` is (BR-93). An evaluation result has to outlive the
query log it came from - six months on, the Recall figure still means something
after the logs have been pruned, and RESTRICT would make pruning impossible.

Revision ID: 0003_evaluation
Revises: 0002_query
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_evaluation"
down_revision = "0002_query"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- E19 evaluation_run ----
    op.create_table(
        "evaluation_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        # retrieval_only | full  (BR-119)
        sa.Column("mode", sa.String(16), nullable=False),
        # running | partial | succeeded | failed
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("golden_set_path", sa.String(512), nullable=False),
        # The golden set lives in the repository, not here (BR-111). The hash is
        # what lets a resume refuse to continue across an edited file.
        sa.Column("golden_set_hash", sa.String(64), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("embedding_model", sa.String(128), nullable=True),
        sa.Column("answer_model", sa.String(128), nullable=True),
        sa.Column("judge_model", sa.String(128), nullable=True),
        sa.Column(
            "prompt_versions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "corpus_fingerprint",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "baseline_id",
            sa.Integer(),
            sa.ForeignKey("evaluation_run.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_eval_run_baseline", "evaluation_run", ["is_baseline", "finished_at"]
    )

    # ---- E20 evaluation_item ----
    op.create_table(
        "evaluation_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("evaluation_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_id", sa.String(64), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("expects", sa.String(8), nullable=False),
        # done | skipped | quota_exhausted | failed  (BR-118)
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "query_id",
            sa.BigInteger(),
            sa.ForeignKey("query_log.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column(
            "retrieved", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("recall_at_5", sa.Numeric(4, 3), nullable=True),
        sa.Column("recall_at_10", sa.Numeric(4, 3), nullable=True),
        sa.Column("reciprocal_rank", sa.Numeric(4, 3), nullable=True),
        sa.Column("citation_precision", sa.Numeric(4, 3), nullable=True),
        sa.Column("refusal_correct", sa.Boolean(), nullable=True),
        sa.Column("judge_correct", sa.Boolean(), nullable=True),
        sa.Column("judge_faithful", sa.Boolean(), nullable=True),
        sa.Column("judge_reason", sa.Text(), nullable=True),
        sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_ms", sa.Integer(), nullable=True),
        sa.Column("error_kind", sa.String(64), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # A resume must not be able to score the same question twice (BR-117).
        sa.UniqueConstraint("run_id", "question_id", name="uq_eval_item_question"),
    )
    op.create_index("ix_eval_item_run_status", "evaluation_item", ["run_id", "status"])


def downgrade() -> None:
    # Safe precisely because nothing else was touched.
    op.drop_index("ix_eval_item_run_status", table_name="evaluation_item")
    op.drop_table("evaluation_item")
    op.drop_index("ix_eval_run_baseline", table_name="evaluation_run")
    op.drop_table("evaluation_run")
