"""Give an account a role - B3.

u5 shipped accounts and stopped there: every screen either asks for a login or
does not, and "logged in" was the only distinction the system could make. That
is not enough for the admin screens. Measured 2026-09-02: `/admin`,
`/admin/sources`, `/admin/jobs`, `/usage` and the whole `/api/*` prefix answer
**200 to an anonymous request**, and `POST /api/sources/{id}/ingest` reaches a
state change without authenticating. Requiring a login on those would close the
anonymous hole and open a different one - every registered user, on a system
where registration is open, would then run ingest jobs and read the cost
figures. The missing concept is not authentication, it is a role.

One column, `'user'` for everyone. `server_default` rather than a backfill
because it has to be right for rows this migration cannot see: `user_account`
holds **0 rows** today, but the default is what makes the column correct on any
database this is applied to later, including one restored from a backup taken
after accounts exist. NOT NULL with a default is the pair that leaves no row
without an answer.

Nobody becomes an admin by running this. Promotion is a separate, explicit act
(`safeenv grant-admin <email>`) - deliberately not "the first account is the
admin", which on an exposed instance hands the role to whoever registers first.

Revision ID: 0006_role
Revises: 0005_build_id
Create Date: 2026-09-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_role"
down_revision = "0005_build_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_account",
        # String, not a native enum type, like every other short-value column
        # here (domain-entities.md section 2): psql output stays readable and
        # adding a third role later is an UPDATE, not an ALTER TYPE.
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
    )


def downgrade() -> None:
    op.drop_column("user_account", "role")
