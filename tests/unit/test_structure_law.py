"""Statute structuring — BR-21, BR-22, BR-23."""

from __future__ import annotations

from app.core.types import StructureStatus
from app.processing.structure.law import clause_numbers, find_sections


class TestArticleSplitting:
    def test_articles_become_sections(self, law_text):
        sections, status = find_sections(law_text)
        assert status is StructureStatus.STRUCTURED
        codes = [s.section_code for s in sections]
        assert "제1조" in codes
        assert "제12조" in codes

    def test_sub_numbered_article_is_separate(self, law_text):
        """제12조의2 is its own article, not part of 제12조."""
        codes = [s.section_code for s in find_sections(law_text)[0]]
        assert "제12조의2" in codes
        assert codes.index("제12조") < codes.index("제12조의2")

    def test_article_title_is_extracted(self, law_text):
        sections, _ = find_sections(law_text)
        by_code = {s.section_code: s.section_title for s in sections}
        assert by_code["제12조"] == "취급시설의 기준"

    def test_article_body_stays_with_its_article(self, law_text):
        """BR-22 — paragraphs live inside the article chunk, not beside it."""
        sections, _ = find_sections(law_text)
        article12 = next(s for s in sections if s.section_code == "제12조")
        body = law_text[article12.start_offset : article12.end_offset]
        assert "①" in body and "②" in body and "③" in body
        # and it stops before the next article
        assert "제12조의2" not in body

    def test_sections_are_ordered_and_contiguous(self, law_text):
        sections, _ = find_sections(law_text)
        for previous, current in zip(sections, sections[1:], strict=False):
            assert previous.end_offset == current.start_offset
        assert sections[-1].end_offset == len(law_text)


class TestAddendaAndAppendices:
    def test_addendum_is_its_own_section(self, law_text):
        """BR-23 — folding 부칙 into the last article would make that article
        claim text that is not part of it."""
        codes = [s.section_code for s in find_sections(law_text)[0]]
        assert "부칙" in codes

    def test_appendix_is_its_own_section(self, law_text):
        codes = [s.section_code for s in find_sections(law_text)[0]]
        assert any(c.startswith("별표") for c in codes)

    def test_last_article_does_not_swallow_the_addendum(self, law_text):
        sections, _ = find_sections(law_text)
        article13 = next(s for s in sections if s.section_code == "제13조")
        body = law_text[article13.start_offset : article13.end_offset]
        assert "부칙" not in body


class TestClauseNumbers:
    def test_circled_numerals_are_collected(self):
        assert clause_numbers("① 첫째 ② 둘째 ③ 셋째") == ["1", "2", "3"]

    def test_written_paragraph_references_are_collected(self):
        assert clause_numbers("제1항에 따른 사항은 제2항으로 정한다") == ["1", "2"]

    def test_duplicates_are_removed_but_order_kept(self):
        assert clause_numbers("① 가 ② 나 ① 다") == ["1", "2"]

    def test_no_clauses_returns_empty(self):
        assert clause_numbers("본문만 있는 조문") == []


class TestNoMatch:
    def test_text_without_articles_is_unstructured(self):
        sections, status = find_sections("아무 조문도 없는 일반 문서입니다.")
        assert status is StructureStatus.UNSTRUCTURED
        assert sections == []
