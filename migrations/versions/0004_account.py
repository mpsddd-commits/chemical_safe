"""u5 account and upload schema - entity E21.

One new table and three nullable columns. **Nothing existing is altered**, and
that is the point of the groundwork u1 laid: `document.owner_id`,
`chunk.owner_id` and `query_log.owner_id` have been there since 0001, always
NULL, and `apply_scope` has been filtering on them since u1. This unit puts
values in them.

`document.owner_id` gets **no foreign key** to `user_account`. The column
predates this table by four units, and adding the constraint now would force a
decision about what happens to a user's documents when their account is deleted
- a feature that does not exist (FR has no account deletion). Absent features do
not get cascade rules.

Revision ID: 0004_account
Revises: 0003_evaluation
Create Date: 2026-08-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_account"
down_revision = "0003_evaluation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- E21 user_account ----
    op.create_table(
        "user_account",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Lower-cased before it gets here (BR-132). UNIQUE on the raw value would
        # let A@x.com and a@x.com be two accounts, and then one person's uploads
        # are invisible from their other login - an isolation bug that is not one.
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        # argon2id (NFR-11, BR-131). Length allows for future parameter growth.
        sa.Column("password_hash", sa.String(255), nullable=False),
        # FR-34's other half: u2 shipped the always-visible disclaimer (FR-35),
        # the record of consent needed an account.
        sa.Column("disclaimer_version", sa.String(16), nullable=False),
        sa.Column(
            "disclaimer_agreed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        # AP-2 - exponential backoff state. A delay, not a lockout: a lockout
        # lets anyone who knows an address deny that account service.
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ---- document: upload metadata ----
    # All nullable, so the 78 collected documents stay valid untouched and keep
    # owner_id NULL - they remain public after accounts exist (BR-147).
    op.add_column("document", sa.Column("upload_filename", sa.String(255), nullable=True))
    op.add_column("document", sa.Column("upload_size_bytes", sa.Integer(), nullable=True))
    op.add_column("document", sa.Column("upload_page_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("document", "upload_page_count")
    op.drop_column("document", "upload_size_bytes")
    op.drop_column("document", "upload_filename")
    op.drop_table("user_account")
