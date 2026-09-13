"""Keep the CAS number a source declared for a document, so re-indexing can carry it.

`MsdsPdfAdapter` reads `cas_number` from the manifest and hands it over in
`ref.extra`. `IndexingService.process` writes it onto every chunk as
`meta.cas_number`, which is what BR-38's exact identifier match reads. The
document row did not keep it, and `_raw_from_original` rebuilt `extra` from the
row, so re-indexing from the retained originals stripped the CAS from every
MSDS chunk (measured 2026-09-13: 414 of 445 chunks lost it; msds-02 Recall@5
went 1.0 to 0.0). `title` and `law_name` survive the same round trip only
because they already have columns here, so this gives the third key the same
treatment.

Why a column and not something already stored:

* `document_substance -> substance.cas_number` cannot reproduce it. Two of the
  26 datasheets (염산 7647-01-0, LDPE 25087-34-7) name a CAS the substance
  master does not hold, so they have no link at all, and a mixture datasheet
  links several substances and is the datasheet of none of them.
* Re-reading `config/msds_manifest.json` at re-index time makes the result
  depend on the file as it is today, not on what was collected.
* The chunks' own `meta.cas_number` disappears the moment one bad re-index
  runs, which is exactly how it was lost.

The backfill copies the value the chunks already carry, and only where it can
only have come from `ref.extra`: a JSON original has a payload, and a payload
CAS wins over `extra` in `process`, so those documents are left NULL (their
CAS is re-read from the payload on re-index). A document whose chunks disagree,
or carry no CAS at all, stays NULL rather than having one guessed - the mixture
datasheet is the case that rule protects. A database whose chunks already lost
the value backfills nothing here; seed it from a backup taken before the loss.

Revision ID: 0009_document_cas_number
Revises: 0008_synonym_source_document
Create Date: 2026-09-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_document_cas_number"
down_revision = "0008_synonym_source_document"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document", sa.Column("cas_number", sa.String(20), nullable=True))
    op.execute(
        """
        UPDATE document d
        SET cas_number = agreed.cas
        FROM (
            SELECT c.document_id, MIN(c.meta->>'cas_number') AS cas
            FROM chunk c
            GROUP BY c.document_id
            HAVING COUNT(*) = COUNT(c.meta->>'cas_number')
               AND COUNT(DISTINCT c.meta->>'cas_number') = 1
        ) agreed
        WHERE agreed.document_id = d.id
          AND d.original_media_type IS DISTINCT FROM 'application/json'
        """
    )


def downgrade() -> None:
    op.drop_column("document", "cas_number")
