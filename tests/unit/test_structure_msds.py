"""MSDS section recognition — BR-15 ~ BR-20.

The case that matters most is BR-20: a document whose sections cannot be
recognised must still be indexed, just without section metadata. Failing to
parse is not a licence to lose the document.
"""

from __future__ import annotations

from app.core.types import DocType, StructureStatus
from app.processing.stages.structure import structure
from app.processing.structure.msds import find_sections


class TestRecognition:
    def test_all_sixteen_sections_found(self, msds_text):
        sections, status = find_sections(msds_text, min_sections=8)
        assert status is StructureStatus.STRUCTURED
        assert len(sections) == 16

    def test_section_codes_are_canonical(self, msds_text):
        sections, _ = find_sections(msds_text, min_sections=8)
        codes = [s.section_code for s in sections]
        assert codes[0] == "msds_01"
        assert "msds_08" in codes
        assert codes[-1] == "msds_16"

    def test_titles_come_from_the_canonical_table(self, msds_text):
        sections, _ = find_sections(msds_text, min_sections=8)
        by_code = {s.section_code: s.section_title for s in sections}
        assert by_code["msds_08"] == "노출방지 및 개인보호구"

    def test_sections_are_contiguous_and_ordered(self, msds_text):
        """BR-17 — each section runs to the next header, the last to end of text."""
        sections, _ = find_sections(msds_text, min_sections=8)
        for previous, current in zip(sections, sections[1:], strict=False):
            assert previous.end_offset == current.start_offset
            assert previous.ordinal < current.ordinal
        assert sections[-1].end_offset == len(msds_text)

    def test_offsets_slice_back_to_the_header(self, msds_text):
        sections, _ = find_sections(msds_text, min_sections=8)
        first = sections[0]
        assert msds_text[first.start_offset : first.end_offset].startswith("1.")


class TestNumberAndTitleMustAgree:
    def test_bare_number_is_not_a_header(self):
        """BR-16 — a numbered list item must not be mistaken for a section."""
        text = "\n".join(
            [
                "1. 화학제품과 회사에 관한 정보",
                "제품명: 시험물질",
                "2. 유해성·위험성",
                "다음 각 호를 지킬 것",
                "3. 보호구를 착용할 것",  # numbered list, not section 3
                "4. 응급조치 요령",
                "즉시 세척한다",
            ]
        )
        sections, _ = find_sections(text, min_sections=1)
        codes = [s.section_code for s in sections]
        assert codes == ["msds_01", "msds_02", "msds_04"]

    def test_alternate_numbering_styles_are_accepted(self):
        text = "1) 화학제품과 회사에 관한 정보\n내용\n제2항 유해성·위험성\n내용"
        sections, _ = find_sections(text, min_sections=1)
        assert [s.section_code for s in sections] == ["msds_01", "msds_02"]


class TestToleranceRules:
    def test_gaps_are_kept_as_is(self, msds_text):
        """BR-18 — a document that skips section 5 keeps the rest."""
        without_five = msds_text.replace("5. 폭발·화재시 대처방법", "폭발·화재시 대처방법")
        sections, status = find_sections(without_five, min_sections=8)
        assert status is StructureStatus.STRUCTURED
        assert "msds_05" not in [s.section_code for s in sections]
        assert len(sections) == 15

    def test_duplicate_number_keeps_the_first(self):
        """BR-19 — a later repeat becomes body text of the first occurrence."""
        text = (
            "1. 화학제품과 회사에 관한 정보\n제품명: A\n"
            "2. 유해성·위험성\n위험\n"
            "1. 화학제품과 회사에 관한 정보\n중복된 머리글\n"
        )
        sections, _ = find_sections(text, min_sections=1)
        assert [s.section_code for s in sections] == ["msds_01", "msds_02"]
        assert "중복된 머리글" in text[sections[1].start_offset : sections[1].end_offset]


class TestFallback:
    def test_below_threshold_becomes_unstructured(self, msds_unstructured_text):
        """BR-20 — under MSDS_MIN_SECTIONS, no sections are emitted."""
        sections, status = find_sections(msds_unstructured_text, min_sections=8)
        assert status is StructureStatus.UNSTRUCTURED
        assert sections == []

    def test_dispatch_never_raises_on_unparseable_input(self, settings):
        """BR-24 — structure failure must not abort the pipeline."""
        doc = structure("", DocType.MSDS, settings)
        assert doc.structure_status is StructureStatus.UNSTRUCTURED
        assert doc.sections == []

    def test_threshold_is_configurable(self, msds_unstructured_text):
        sections, status = find_sections(msds_unstructured_text, min_sections=1)
        # Loosening the threshold does not invent sections that are not there.
        assert status is StructureStatus.UNSTRUCTURED
        assert sections == []
