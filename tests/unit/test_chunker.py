"""Chunking — BR-26 ~ BR-31.

The invariant worth guarding hardest is BR-30: a chunk's text must be exactly
the slice its offsets describe. Citation snippets in u2 are produced by slicing
`extracted_text` with those offsets, so if this drifts, every citation is wrong
in a way that is invisible until someone checks the source.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from app.core.config import get_settings
from app.core.types import ChunkMeta, DocType, Section, StructuredDoc, StructureStatus
from app.processing.chunker import chunk_document
from app.processing.structure.msds import find_sections
from app.processing.tokens import count_tokens


@pytest.fixture
def base_meta() -> ChunkMeta:
    return ChunkMeta(doc_type="msds", source_url="https://example.test/doc")


def _structured(text: str) -> StructuredDoc:
    sections, status = find_sections(text, min_sections=8)
    return StructuredDoc(doc_type=DocType.MSDS, sections=sections, structure_status=status)


class TestSectionAlignment:
    def test_one_section_becomes_one_chunk(self, msds_text, base_meta, settings):
        doc = _structured(msds_text)
        chunks = chunk_document(msds_text, doc, base_meta, settings)
        # No section in the fixture exceeds the token ceiling.
        assert len(chunks) == len(doc.sections)

    def test_section_metadata_rides_on_the_chunk(self, msds_text, base_meta, settings):
        doc = _structured(msds_text)
        chunks = chunk_document(msds_text, doc, base_meta, settings)
        codes = {c.meta.section_code for c in chunks}
        assert "msds_08" in codes
        ppe = next(c for c in chunks if c.meta.section_code == "msds_08")
        assert ppe.meta.section_title == "노출방지 및 개인보호구"
        assert "내산성 장갑" in ppe.text

    def test_base_metadata_is_preserved(self, msds_text, base_meta, settings):
        doc = _structured(msds_text)
        chunks = chunk_document(msds_text, doc, base_meta, settings)
        assert all(c.meta.source_url == "https://example.test/doc" for c in chunks)
        assert all(c.meta.doc_type == "msds" for c in chunks)


class TestOffsetIntegrity:
    def test_chunk_text_equals_its_slice(self, msds_text, base_meta, settings):
        """BR-30 — the whole citation mechanism rests on this."""
        doc = _structured(msds_text)
        for chunk in chunk_document(msds_text, doc, base_meta, settings):
            assert chunk.text == msds_text[chunk.start_offset : chunk.end_offset]

    def test_offsets_are_ordered_and_non_overlapping(self, msds_text, base_meta, settings):
        doc = _structured(msds_text)
        chunks = chunk_document(msds_text, doc, base_meta, settings)
        for previous, current in zip(chunks, chunks[1:], strict=False):
            assert previous.end_offset <= current.start_offset
            assert previous.ordinal < current.ordinal

    def test_no_overlap_between_chunks(self, msds_text, base_meta, settings):
        """BR-29 — overlap would let one passage be cited twice as two sources."""
        doc = _structured(msds_text)
        chunks = chunk_document(msds_text, doc, base_meta, settings)
        spans = [(c.start_offset, c.end_offset) for c in chunks]
        for (_, prev_end), (next_start, _) in zip(spans, spans[1:], strict=False):
            assert next_start >= prev_end


class TestSizeRules:
    def test_oversized_section_is_split_at_paragraphs(self, base_meta, settings):
        """BR-27 — splitting happens only above the ceiling, at blank lines."""
        paragraph = "가" * 400
        text = "\n\n".join([paragraph] * 10)
        doc = StructuredDoc(
            doc_type=DocType.MSDS,
            sections=[Section(0, "msds_01", "제품 정보", 0, len(text))],
            structure_status=StructureStatus.STRUCTURED,
        )
        tight = settings.model_copy(update={"max_chunk_tokens": 400})
        chunks = chunk_document(text, doc, base_meta, tight)
        assert len(chunks) > 1
        # every split piece still belongs to the same section
        assert {c.section_ordinal for c in chunks} == {0}
        assert {c.meta.section_code for c in chunks} == {"msds_01"}

    def test_no_chunk_exceeds_the_ceiling(self, base_meta, settings):
        paragraph = "나" * 300
        text = "\n\n".join([paragraph] * 12)
        doc = StructuredDoc(
            doc_type=DocType.MSDS,
            sections=[Section(0, "msds_01", None, 0, len(text))],
            structure_status=StructureStatus.STRUCTURED,
        )
        chunks = chunk_document(text, doc, base_meta, settings)
        for chunk in chunks:
            assert chunk.token_count <= settings.max_chunk_tokens

    def test_tiny_trailing_fragment_is_merged(self, base_meta, settings):
        """BR-31 — a stray fragment joins the section it followed."""
        text = "본문 내용이 충분히 긴 문단입니다. " * 20 + "\n\n짧음"
        doc = StructuredDoc(
            doc_type=DocType.MSDS,
            sections=[Section(0, "msds_01", None, 0, len(text))],
            structure_status=StructureStatus.STRUCTURED,
        )
        chunks = chunk_document(text, doc, base_meta, settings)
        assert all(
            c.token_count >= settings.min_chunk_tokens or len(chunks) == 1 for c in chunks
        )
        assert chunks[-1].text.endswith("짧음")


class TestBoundaryLadder:
    """BR-27a — descend to a finer boundary when blank lines are absent.

    Every case here was measured on the real corpus, where 27 chunks sat above
    `MAX_CHUNK_TOKENS` and the largest held 8,111 tokens against a ceiling of
    1,000. `EMBED_MAX_SEQ_LENGTH` is 2,048, so anything past it never reached the
    vector while its BR-30 offsets still pointed at it — citable, unsearchable.
    """

    @staticmethod
    def _one_section(text: str) -> StructuredDoc:
        return StructuredDoc(
            doc_type=DocType.MSDS,
            sections=[Section(0, "msds_11", "독성에 관한 정보", 0, len(text))],
            structure_status=StructureStatus.STRUCTURED,
        )

    def test_single_newline_rows_are_split(self, base_meta, settings):
        """MSDS section 11 arrives as ~80 rows with no blank line between them."""
        rows = [f"○ 노출경로 {i} : " + "가" * 120 for i in range(20)]
        text = "\n".join(rows)
        tight = settings.model_copy(update={"max_chunk_tokens": 200})
        chunks = chunk_document(text, self._one_section(text), base_meta, tight)

        assert len(chunks) > 1
        assert all(c.token_count <= 200 for c in chunks)
        # cuts landed on row boundaries, not inside a row
        assert all(c.text.startswith("○") for c in chunks)

    def test_single_line_statute_is_split_at_sentences(self, base_meta, settings):
        """법령 부칙 comes back from the API as one line with no newline at all."""
        sentences = [
            f"제{i}조(시행일) 이 영은 공포 후 6개월이 경과한 날부터 시행한다." for i in range(1, 30)
        ]
        text = " ".join(sentences)
        assert "\n" not in text
        tight = settings.model_copy(update={"max_chunk_tokens": 200})
        chunks = chunk_document(text, self._one_section(text), base_meta, tight)

        assert len(chunks) > 1
        assert all(c.token_count <= 200 for c in chunks)
        assert all(c.text.endswith(".") for c in chunks)

    def test_text_with_no_separator_is_hard_sliced(self, base_meta, settings):
        """Last rung. Ugly, but a silent embedding truncation is worse."""
        text = "가" * 3000
        tight = settings.model_copy(update={"max_chunk_tokens": 200})
        chunks = chunk_document(text, self._one_section(text), base_meta, tight)

        assert all(c.token_count <= 200 for c in chunks)
        # nothing is dropped: there were no separators to discard
        assert "".join(c.text for c in chunks) == text

    def test_coarsest_usable_boundary_wins(self, base_meta, settings):
        """A finer rung only runs when the one above leaves a span oversized."""
        paragraphs = ["문단 시작\n" + "가" * 150 for _ in range(10)]
        text = "\n\n".join(paragraphs)
        tight = settings.model_copy(update={"max_chunk_tokens": 200})
        chunks = chunk_document(text, self._one_section(text), base_meta, tight)

        assert all(c.token_count <= 200 for c in chunks)
        # each paragraph fits, so no chunk begins mid-paragraph
        assert all(c.text.startswith("문단 시작") for c in chunks)

    def test_packing_measures_the_merged_slice_not_the_sum(self, base_meta, settings):
        """The separators between spans belong to the chunk but to no span.

        `token_count` is computed on `text[start:end]`, so packing by summing the
        parts understates it — by 6 tokens across 39 sentences, measured. That gap
        is exactly what put 15 real chunks over a ceiling we thought we enforced.
        """
        sentences = [
            f"제{i}조(시행일) 이 영은 공포 후 6개월이 경과한 날부터 시행한다." for i in range(1, 40)
        ]
        text = " ".join(sentences)
        tight = settings.model_copy(update={"max_chunk_tokens": 300})
        chunks = chunk_document(text, self._one_section(text), base_meta, tight)

        for chunk in chunks:
            assert chunk.token_count <= 300
            # the stored count is the slice's count, which is what must fit
            assert count_tokens(text[chunk.start_offset : chunk.end_offset]) <= 300

    def test_undersized_merge_does_not_breach_the_ceiling(self, base_meta, settings):
        """BR-31 yields to BR-27a — measured on 15 chunks that overflowed by 1-18."""
        text = "가" * 260 + "\n\n짧음"
        tight = settings.model_copy(update={"max_chunk_tokens": 200})
        chunks = chunk_document(text, self._one_section(text), base_meta, tight)

        assert all(c.token_count <= 200 for c in chunks)
        # the scrap stays undersized and alone rather than pushing the ceiling
        assert chunks[-1].text == "짧음"
        assert chunks[-1].token_count < tight.min_chunk_tokens

    def test_ladder_preserves_the_offset_invariant(self, base_meta, settings):
        """BR-30 survives every rung — the ladder only slices, never rewrites."""
        cases = [
            "\n".join(f"○ 행 {i} " + "나" * 120 for i in range(15)),
            " ".join(f"제{i}조 이 법은 시행한다." for i in range(1, 25)),
            "다" * 2000,
        ]
        tight = settings.model_copy(update={"max_chunk_tokens": 150})
        for text in cases:
            for chunk in chunk_document(text, self._one_section(text), base_meta, tight):
                assert chunk.text == text[chunk.start_offset : chunk.end_offset]
                assert chunk.token_count == count_tokens(chunk.text)


class TestUnstructuredFallback:
    def test_paragraph_chunking_when_unstructured(
        self, msds_unstructured_text, base_meta, settings
    ):
        """BR-28 — the document is still indexed, just without section codes."""
        doc = StructuredDoc(
            doc_type=DocType.MSDS, sections=[], structure_status=StructureStatus.UNSTRUCTURED
        )
        chunks = chunk_document(msds_unstructured_text, doc, base_meta, settings)
        assert chunks
        assert all(c.section_ordinal is None for c in chunks)
        assert all(c.meta.section_code is None for c in chunks)
        assert all(c.meta.structure_status == "unstructured" for c in chunks)

    def test_fallback_still_satisfies_the_offset_invariant(
        self, msds_unstructured_text, base_meta, settings
    ):
        doc = StructuredDoc(
            doc_type=DocType.MSDS, sections=[], structure_status=StructureStatus.UNSTRUCTURED
        )
        for chunk in chunk_document(msds_unstructured_text, doc, base_meta, settings):
            assert chunk.text == msds_unstructured_text[chunk.start_offset : chunk.end_offset]


class TestProperties:
    """NFR-27 — chunking is pure, so the invariants can be fuzzed."""

    @hyp_settings(max_examples=40, deadline=None)
    @given(
        paragraphs=st.lists(
            st.text(alphabet="가나다라 abcdef.\n", min_size=1, max_size=200),
            min_size=1,
            max_size=12,
        )
    )
    def test_offsets_always_reproduce_the_text(self, paragraphs):
        base_meta = ChunkMeta(doc_type="msds", source_url="https://example.test/doc")
        settings = get_settings()
        text = "\n\n".join(paragraphs)
        doc = StructuredDoc(
            doc_type=DocType.MSDS, sections=[], structure_status=StructureStatus.UNSTRUCTURED
        )
        for chunk in chunk_document(text, doc, base_meta, settings):
            assert chunk.text == text[chunk.start_offset : chunk.end_offset]

    @hyp_settings(max_examples=200, deadline=None)
    @given(
        # Separator-rich alphabets are the interesting shapes: separators are what
        # the sum-of-parts bug hid behind, so they need to be over-represented.
        text=st.text(alphabet="가나다라 abc. \n", min_size=1, max_size=900)
    )
    def test_ceiling_is_an_invariant(self, text):
        """BR-27a — no input shape may produce a chunk above the ceiling."""
        base_meta = ChunkMeta(doc_type="msds", source_url="https://example.test/doc")
        tight = get_settings().model_copy(update={"max_chunk_tokens": 60})
        doc = StructuredDoc(
            doc_type=DocType.MSDS,
            sections=[Section(0, "msds_01", None, 0, len(text))],
            structure_status=StructureStatus.STRUCTURED,
        )
        for chunk in chunk_document(text, doc, base_meta, tight):
            assert chunk.token_count <= 60
            assert chunk.text == text[chunk.start_offset : chunk.end_offset]

    @hyp_settings(max_examples=40, deadline=None)
    @given(text=st.text(alphabet="가나다 abc\n", min_size=0, max_size=400))
    def test_never_raises_and_never_emits_blank_chunks(self, text):
        base_meta = ChunkMeta(doc_type="msds", source_url="https://example.test/doc")
        settings = get_settings()
        doc = StructuredDoc(
            doc_type=DocType.MSDS, sections=[], structure_status=StructureStatus.UNSTRUCTURED
        )
        chunks = chunk_document(text, doc, base_meta, settings)
        assert all(c.text.strip() for c in chunks)
