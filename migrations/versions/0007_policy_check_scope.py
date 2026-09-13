"""Say what a policy_check row is about, and which job it belongs to - D8.

Enforcement was right all along: `IngestionOrchestrator._handle_one` checks
every document URL, and `AccessPolicyChecker` judges the origin of that URL.
The audit trail was not. The only row written was `IngestionService.start`
checking the source's `base_url`, so for `msds_pdf` the table said
`https://msds.kosha.or.kr | unknown` while every PDF came from a vendor host
whose own verdict reached the log and nowhere else. Read as "the policy of this
source", that row led to the wrong conclusion on 2026-09-07.

Why columns and not the existing ones. The fix writes one row per document
origin per job next to the existing base_url row, and a reader has to be able
to tell the two apart and to say which run a row belongs to:

* `scope` cannot be derived from `url`. A base_url can be a bare origin
  (`https://msds.kosha.or.kr`), which is exactly what a document-origin row
  looks like. Putting a tag into `reason` would make the audit trail something
  you parse with a regex, which is the kind of reading this fixes.
* `job_id` cannot be recovered from `checked_at`. A verdict is cached per
  origin, so `checked_at` is when it was judged, not when it was enforced; the
  CLI checks `base_url` in `start` before the job row exists, and two jobs of
  one source can overlap.

`scope` gets `server_default='source_base_url'` because every existing row was
written by the one caller that checks base_url - the default is the truth for
them, not a placeholder. `job_id` stays NULL on those rows and on future
base_url rows, which run before a job exists. SET NULL, like `source_id`: an
audit row outlives the job it describes.

Revision ID: 0007_policy_check_scope
Revises: 0006_role
Create Date: 2026-09-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_policy_check_scope"
down_revision = "0006_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policy_check",
        sa.Column(
            "scope", sa.String(32), nullable=False, server_default="source_base_url"
        ),
    )
    op.add_column(
        "policy_check",
        sa.Column("job_id", sa.Integer, sa.ForeignKey("job.id", ondelete="SET NULL")),
    )
    op.create_index("ix_policy_job", "policy_check", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_policy_job", table_name="policy_check")
    op.drop_column("policy_check", "job_id")
    op.drop_column("policy_check", "scope")
