"""Record which document published a synonym, and own rows by document - D11 follow-up.

`substance_synonym` had two producers told apart by `term_type`: the NCIS
projection writes `ko`/`en`, and D11 wrote `msds_title`/`common_name`/`formula`
from MSDS documents. Owning rows by type was enough while each type had one
producer. It is not enough for the MSDS types: one substance has several MSDS
documents (황산 has two), and re-indexing one of them while replacing every
`common_name` of the substance would delete the names the other document gave.
The accident D11 fixed between producers would recur one level down, between
documents.

So the owner of an MSDS-derived row is the document that printed the name.

* `source_document_id` is nullable. `ko`/`en` rows mirror `substance.name_ko` /
  `name_en`, and the owner of that fact is the substance row, not a document:
  the substance is upserted by CAS (BR-98) and outlives any one record document.
  Tying those rows to a document would delete the names of a substance that
  still exists when the record document is removed. NULL says "owned by the
  substance", and the projection replaces exactly the NULL-owner rows of its
  types.
* ON DELETE CASCADE. A name is evidence only while the document that prints it
  exists; a row whose document is gone would be a name nobody can check (NFR-8).
* The unique key gains the document, `NULLS NOT DISTINCT`. Two MSDS documents
  printing the same name for the same substance are two pieces of evidence, and
  each must survive the other's re-index. NULLS NOT DISTINCT keeps the old
  guarantee for the substance-owned `ko`/`en` rows, where NULL would otherwise
  make every row distinct (PostgreSQL 15+; the image is pg16).

**The existing MSDS-derived rows are deleted, not guessed.** The 45 rows D11
inserted were written by `scripts/backfill_synonyms.py` with no document
recorded. Matching each back to a document here would mean re-running the
extraction inside a migration, and the revised BR-99 also rejects some of them
(strings joined across a line break). BR-97 puts the producer of these rows in
the indexing path, so the rows are restored by re-indexing the MSDS documents
from their retained originals - the same path that must reproduce them after a
restore. `downgrade` cannot bring them back either; re-index instead.

Revision ID: 0008_synonym_source_document
Revises: 0007_policy_check_scope
Create Date: 2026-09-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_synonym_source_document"
down_revision = "0007_policy_check_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "substance_synonym",
        sa.Column(
            "source_document_id",
            sa.Integer,
            sa.ForeignKey("document.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_synonym_source_document", "substance_synonym", ["source_document_id"])

    # Rows no document owns and the projection does not produce (see docstring).
    op.execute(
        "DELETE FROM substance_synonym "
        "WHERE source_document_id IS NULL AND term_type NOT IN ('ko', 'en')"
    )

    op.drop_constraint("uq_synonym_term", "substance_synonym", type_="unique")
    op.create_unique_constraint(
        "uq_synonym_term",
        "substance_synonym",
        ["substance_id", "normalized_term", "term_type", "source_document_id"],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    # Document-owned rows cannot fit the old key (two documents, one name).
    op.execute("DELETE FROM substance_synonym WHERE source_document_id IS NOT NULL")
    op.drop_constraint("uq_synonym_term", "substance_synonym", type_="unique")
    op.create_unique_constraint(
        "uq_synonym_term", "substance_synonym", ["substance_id", "normalized_term", "term_type"]
    )
    op.drop_index("ix_synonym_source_document", table_name="substance_synonym")
    op.drop_column("substance_synonym", "source_document_id")
