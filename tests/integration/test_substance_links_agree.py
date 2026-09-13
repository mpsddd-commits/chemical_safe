"""D12 invariant against the live database - read-only.

`chunk.meta.substance_ids` is BR-36's denormalised copy of `document_substance`.
After any re-index the two must agree, chunk by chunk, as sets. This runs the
check over the whole corpus; nothing here writes.

The query is proven on hand-made rows first (CTEs named after the tables shadow
them), so a green run over the corpus means "no disagreement", not "a query that
cannot see one".
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.engine import session_scope
from app.db.repositories.documents import DocumentRepo

pytestmark = pytest.mark.integration

# One row per disagreeing document. `{sources}` is empty for the real tables.
INVARIANT_SQL = """
WITH {sources}
linked AS (
    SELECT document_id,
           array_agg(DISTINCT substance_id ORDER BY substance_id) AS ids
    FROM document_substance
    GROUP BY document_id
),
stamped AS (
    SELECT c.document_id,
           COALESCE(
               (SELECT array_agg(DISTINCT x::bigint ORDER BY x::bigint)
                FROM jsonb_array_elements_text(
                    COALESCE(c.meta->'substance_ids', '[]'::jsonb)) AS x),
               '{{}}'::bigint[]) AS ids
    FROM chunk c
)
SELECT s.document_id,
       count(*)                            AS disagreeing_chunks,
       min(s.ids::text)                    AS chunk_ids_sample,
       COALESCE(l.ids::text, '{{}}')       AS document_substance_ids
FROM stamped s
LEFT JOIN linked l USING (document_id)
WHERE s.ids IS DISTINCT FROM COALESCE(l.ids, '{{}}'::bigint[])
GROUP BY s.document_id, l.ids
ORDER BY s.document_id
"""

# Document 24 as D13 left it (links kept, chunks emptied), one document whose
# chunks list a substance twice in another order (agrees), one unlinked
# document with empty chunks (agrees), one chunk stamped with nothing linked.
_FAKE_SOURCES = """
chunk(id, document_id, meta) AS (VALUES
    (1, 24, '{"substance_ids": []}'::jsonb),
    (2, 24, '{"substance_ids": [43]}'::jsonb),
    (3, 30, '{"substance_ids": [9, 7, 9]}'::jsonb),
    (4, 31, '{"substance_ids": []}'::jsonb),
    (5, 32, '{}'::jsonb),
    (6, 33, '{"substance_ids": [5]}'::jsonb)
),
document_substance(document_id, substance_id) AS (VALUES
    (24, 43), (30, 7), (30, 9)
),
"""


def _run(session, sources: str) -> list:
    return session.execute(text(INVARIANT_SQL.format(sources=sources))).all()


def test_the_query_sees_a_disagreement():
    with session_scope() as session:
        rows = _run(session, _FAKE_SOURCES)
    assert [(r.document_id, r.disagreeing_chunks) for r in rows] == [(24, 1), (33, 1)]


def test_no_document_disagrees_in_the_corpus():
    with session_scope() as session:
        rows = _run(session, "")
    assert rows == [], f"chunks disagree with document_substance: {rows}"


def test_repository_reads_the_same_links_the_invariant_compares():
    """`linked_substance_ids` is what re-indexing stamps; it must match the table."""
    with session_scope() as session:
        expected = {
            doc: sorted(ids)
            for doc, ids in session.execute(
                text(
                    "SELECT document_id, array_agg(substance_id) FROM document_substance "
                    "GROUP BY document_id"
                )
            ).all()
        }
        repo = DocumentRepo(session)
        actual = {doc: repo.linked_substance_ids(doc) for doc in expected}
    assert expected, "no document_substance rows - the corpus is not indexed"
    assert actual == expected


def test_substance_links_carry_the_tables_relations():
    """D14 - the synonym step reads relations through this; it must be the table."""
    with session_scope() as session:
        expected: dict[int, list[tuple[int, str]]] = {}
        for doc, sid, relation in session.execute(
            text(
                "SELECT document_id, substance_id, relation FROM document_substance "
                "ORDER BY document_id, substance_id"
            )
        ).all():
            expected.setdefault(doc, []).append((sid, relation))
        repo = DocumentRepo(session)
        actual = {
            doc: [(sid, rel.value) for sid, rel in repo.substance_links(doc)] for doc in expected
        }
        ids = {doc: repo.linked_substance_ids(doc) for doc in expected}
    assert expected, "no document_substance rows - the corpus is not indexed"
    assert actual == expected
    assert ids == {doc: [sid for sid, _r in links] for doc, links in expected.items()}
