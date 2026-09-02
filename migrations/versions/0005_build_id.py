"""Record which code produced each evaluation run - defect 58.

`EvaluationRun` has recorded the model, the prompt versions, the config and the
corpus since 0003, and its own docstring says a run is useless unless you can
tell what moved: "the model, the prompt, the corpus, or the code". The code was
the one thing it did not record, and on 2026-08-30 that was exactly the thing
that had moved - the containers were running a five-hour-old image while the
tests ran the working tree.

One nullable column. Existing runs keep NULL, which is the truthful value: for
runs 1-153 nobody recorded what code produced them and this migration cannot
invent it.

Deliberately **not** added to `reporter._COMPARABLE_FIELDS`. Two runs on
different code are the normal case for a regression guard - detecting the
effect of a code change is what the guard is *for*. Making the build id a
comparability field would mark every post-change run `incomparable` and the
guard would never fire again, which is the shape of defect 55.

Revision ID: 0005_build_id
Revises: 0004_account
Create Date: 2026-08-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_build_id"
down_revision = "0004_account"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evaluation_run", sa.Column("build_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluation_run", "build_id")
