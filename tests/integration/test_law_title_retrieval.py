"""Section-title tier against the live corpus (2026-09-02).

A statute question paraphrases the article title; the body-text route cannot
bridge Korean's missing stemmer (the index keeps particles inside lexemes) and
five measured prefix variants all traded existing recall for new. The title
LIKE is the precise instrument: law-08 and law-09 went from recall 0.000 to
1.000 with zero recall regressions (runs 258 vs 283).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.types import Scope
from app.db.engine import session_scope
from app.db.models import ChunkRow
from app.rag.entities import EntityExtractor
from app.rag.retrieval.retrievers import Retrievers

pytestmark = pytest.mark.integration


def _keyword_sections(query: str) -> list[tuple[str | None, str | None]]:
    with session_scope() as session:
        intent = EntityExtractor(session).extract(query)
        result = Retrievers(session, embedder=None).keyword(query, intent, Scope.public())
        assert not result.failed
        by_id = {c.chunk_id: i for i, c in enumerate(result.candidates)}
        rows = session.execute(
            select(ChunkRow.id, ChunkRow.meta).where(ChunkRow.id.in_(by_id))
        ).all()
        ordered = sorted(rows, key=lambda r: by_id[r[0]])
        return [
            ((m or {}).get("section_code"), (m or {}).get("law_name")) for _, m in ordered
        ]


class TestTitleTierReachesTheArticle:
    def test_law_08_finds_the_msds_management_article(self):
        """제114조 "물질안전보건자료의 게시 및 교육" - the compound noun in the
        question appears in the title, never bare in the body lexemes."""
        sections = _keyword_sections(
            "사업주는 물질안전보건자료를 작업장에서 어떻게 관리해야 하나요?"
        )
        top = sections[:8]
        assert ("제114조", "산업안전보건법") in top, top

    def test_law_09_finds_the_psm_target_article(self):
        """제43조 "공정안전보고서의 제출 대상" - reachable only through the
        title: the body tokenises as "공정안전보고서의" and plain matching
        never sees it (measured: 13 plain matches, none of them this chunk)."""
        sections = _keyword_sections(
            "공정안전보고서를 제출해야 하는 업종에는 어떤 것이 있나요?"
        )
        top = sections[:8]
        assert ("제43조", "산업안전보건법") in top, top

    def test_short_terms_do_not_summon_titles(self):
        """"관리", "제출" alone appear in dozens of titles; the 5-char gate is
        what keeps this tier from being the ts_rank reshuffle all over again."""
        from app.indexing.keyword_index import KeywordIndex

        with session_scope() as session:
            index = KeywordIndex(session)
            assert index._title_matches(["관리", "제출", "게시"], Scope.public()) == []

    def test_the_tier_is_capped(self):
        """"유해화학물질" titles ~20 화관법 articles; five may enter."""
        from app.indexing.keyword_index import KeywordIndex

        with session_scope() as session:
            index = KeywordIndex(session)
            hits = index._title_matches(["유해화학물질"], Scope.public())
            assert 0 < len(hits) <= 5
