"""Metadata rules and structure dispatch — BR-24, BR-25, BR-32, BR-33, BR-37.

BR-32 is the one that shapes the whole corpus: a chunk whose origin cannot be
named is worse than a missing chunk, because u2 would cite it.
"""

from __future__ import annotations

import pytest

from app.core.errors import MissingRequiredMetadataError
from app.core.types import (
    ChunkMeta,
    DocType,
    RawDocument,
    SourceRef,
    StructureStatus,
    SubstanceRelation,
)
from app.processing.runner import PipelineRunner
from app.processing.stages.structure import structure


def _raw(url: str = "https://example.test/doc") -> RawDocument:
    ref = SourceRef(source_id="src", external_id="doc-1", url=url)
    return RawDocument(ref=ref, payload={"title": "시험 문서", "body": "본문 내용입니다."},
                       media_type="application/json", stored_path="/tmp/x.json")


class TestRequiredMetadata:
    def test_missing_source_url_refuses_to_index(self, settings):
        """BR-32 — refuse rather than store something untraceable."""
        runner = PipelineRunner(settings)
        meta = ChunkMeta(doc_type="msds", source_url="")
        with pytest.raises(MissingRequiredMetadataError):
            runner.run(_raw(), DocType.MSDS, meta)

    def test_missing_doc_type_refuses_to_index(self, settings):
        runner = PipelineRunner(settings)
        meta = ChunkMeta(doc_type="", source_url="https://example.test/doc")
        with pytest.raises(MissingRequiredMetadataError):
            runner.run(_raw(), DocType.MSDS, meta)

    def test_complete_metadata_proceeds(self, settings):
        runner = PipelineRunner(settings)
        meta = ChunkMeta(doc_type="msds", source_url="https://example.test/doc")
        ctx = runner.run(_raw(), DocType.MSDS, meta)
        assert ctx.chunks
        assert all(c.meta.source_url == "https://example.test/doc" for c in ctx.chunks)


class TestOptionalMetadata:
    def test_absent_optional_fields_stay_none(self):
        """BR-39 / NFR-8 — never invent a value that was not published."""
        meta = ChunkMeta(doc_type="law", source_url="https://example.test/law")
        as_dict = meta.to_dict()
        assert as_dict["published_at"] is None
        assert as_dict["cas_number"] is None
        assert as_dict["un_number"] is None

    def test_meta_round_trips_through_dict(self):
        meta = ChunkMeta(
            doc_type="msds",
            source_url="https://example.test/doc",
            cas_number="7664-93-9",
            substance_names=["황산"],
            clause_numbers=["1", "2"],
        )
        as_dict = meta.to_dict()
        assert as_dict["cas_number"] == "7664-93-9"
        assert as_dict["substance_names"] == ["황산"]
        assert as_dict["clause_numbers"] == ["1", "2"]


class TestRelationMapping:
    @pytest.mark.parametrize(
        ("doc_type", "expected"),
        [
            (DocType.MSDS, SubstanceRelation.SUBJECT),
            (DocType.INCIDENT, SubstanceRelation.MENTIONED),
            (DocType.LAW, SubstanceRelation.REGULATED),
        ],
    )
    def test_relation_follows_document_type(self, doc_type, expected):
        """BR-37 — an MSDS is *about* a substance; an incident merely mentions one."""
        from app.services.indexing_service import _RELATION_BY_DOC_TYPE

        assert _RELATION_BY_DOC_TYPE[doc_type] is expected


class TestStructureDispatch:
    def test_incident_fields_become_sections(self, incident_text, settings):
        doc = structure(incident_text, DocType.INCIDENT, settings)
        assert doc.structure_status is StructureStatus.STRUCTURED
        codes = [s.section_code for s in doc.sections]
        assert "incident_cause" in codes
        assert "incident_action" in codes

    def test_absent_incident_field_produces_no_section(self, settings):
        """BR-25 / NFR-8 — no empty section claiming damage was reported."""
        partial = "accidentNo: 1\noccurred_at: 2024-03-11\nplace: 어딘가"
        doc = structure(partial, DocType.INCIDENT, settings)
        codes = [s.section_code for s in doc.sections]
        assert "incident_damage" not in codes
        assert "incident_where" in codes

    def test_law_dispatch_finds_articles(self, law_text, settings):
        doc = structure(law_text, DocType.LAW, settings)
        assert doc.structure_status is StructureStatus.STRUCTURED
        assert any(s.section_code == "제12조" for s in doc.sections)

    def test_dispatch_never_raises(self, settings):
        """BR-24 — every branch degrades to unstructured rather than throwing."""
        for doc_type in (DocType.MSDS, DocType.LAW, DocType.INCIDENT):
            doc = structure("", doc_type, settings)
            assert doc.structure_status is StructureStatus.UNSTRUCTURED


class TestOriginalMediaType:
    """Regression guard for a defect found in Build & Test.

    Every byte payload was stored as `.pdf` regardless of what it actually was,
    and re-indexing read the media type back from the extension. A text
    original therefore came back labelled as a PDF and failed extraction
    permanently - `document.original_media_type` was recorded but never used.
    """

    @pytest.mark.parametrize(
        ("media_type", "expected"),
        [
            ("application/pdf", ".pdf"),
            ("application/json", ".json"),
            ("text/plain", ".txt"),
            ("text/html", ".html"),
            ("application/xml", ".xml"),
            ("application/octet-stream", ".bin"),
        ],
    )
    def test_suffix_follows_media_type(self, media_type, expected):
        assert PipelineRunner._suffix_for(media_type) == expected

    def test_unknown_media_type_does_not_claim_to_be_pdf(self):
        assert PipelineRunner._suffix_for("application/vnd.made-up") == ".bin"


class TestResumeKeepsStoredOriginal:
    """Regression guard for a defect found in Build & Test.

    Re-indexing resumes at `extract`, which skips `fetch`. The context's
    `stored_path` was therefore left unset and written back as NULL, so the
    document lost its retained original and could never be re-indexed again -
    the resume path destroying the thing resume depends on (BR-44, FQ-8=A).
    """

    def test_stored_path_survives_a_resumed_run(self, settings):
        from app.core.types import PipelineStage

        runner = PipelineRunner(settings)
        raw = _raw()
        raw.stored_path = "/data/originals/src/doc-1.json"
        meta = ChunkMeta(doc_type="msds", source_url="https://example.test/doc")

        ctx = runner.run(raw, DocType.MSDS, meta, from_stage=PipelineStage.EXTRACT)

        assert ctx.stored_path == "/data/originals/src/doc-1.json"

    def test_stored_path_is_set_on_a_full_run(self, settings, tmp_path):
        relocated = settings.model_copy(update={"originals_dir": tmp_path})
        runner = PipelineRunner(relocated)
        raw = _raw()
        raw.stored_path = None
        meta = ChunkMeta(doc_type="msds", source_url="https://example.test/doc")

        ctx = runner.run(raw, DocType.MSDS, meta)

        assert ctx.stored_path is not None
        assert ctx.stored_path.endswith(".json")
