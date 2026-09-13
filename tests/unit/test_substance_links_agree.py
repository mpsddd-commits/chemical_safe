"""D12 - a chunk's `substance_ids` and its document's `document_substance` agree.

2026-09-13: D13 stripped the CAS from MSDS chunks during a re-index, the
substance resolution came back empty, and document 24's 16 chunks lost
`substance_ids` ([43] -> []) while `document_substance` still linked it to 43.
The same fact, written in two places, updated in one.

BR-36 makes the relational table the source and `chunk.meta` its copy. These
tests pin three things, each against a re-index run through `process` with fake
collaborators - no database, no corpus:

(a) an empty resolution keeps the old links, and the chunks carry those links;
(b) a resolution that finds links replaces them, and the chunks carry the new ones;
(c) (a) is never silent - it is logged and reported.

The thing these tests refuse is the tempting "fix": treating the empty result as
"no substances" and deleting the links. D13 shows why - the result was empty
because of a defect, and that fix turns a defect into lost data.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from app.core.types import (
    Chunk,
    ChunkMeta,
    DocType,
    ExtractedText,
    RawDocument,
    SourceRef,
    StructuredDoc,
    StructureStatus,
    SubstanceRelation,
)
from app.services.indexing_service import IndexingService

DOC_ID = 24


class _Documents:
    """`document_substance` for one document, as a dict. Mirrors `DocumentRepo`."""

    def __init__(self, linked: dict[int, str]) -> None:
        self.linked = dict(linked)
        self.link_calls = 0

    def upsert(self, **_kwargs):
        return SimpleNamespace(id=DOC_ID, title="황산 (SULFURIC ACID) - 테스트")

    def set_extracted_text(self, *_args) -> None:
        pass

    def replace_sections(self, *_args):
        return []

    def link_substances(self, document, links) -> None:
        self.link_calls += 1
        self.linked = {}
        for sid, relation in links:
            self.linked.setdefault(sid, relation.value)

    def substance_links(self, document_id: int) -> list[tuple[int, SubstanceRelation]]:
        assert document_id == DOC_ID
        return [(sid, SubstanceRelation(self.linked[sid])) for sid in sorted(self.linked)]

    def linked_substance_ids(self, document_id: int) -> list[int]:
        return [sid for sid, _relation in self.substance_links(document_id)]


class _Chunks:
    """Captures chunk meta at the moment it would be written (BR-54 replace)."""

    def __init__(self) -> None:
        self.written: list[list[int]] = []

    def replace_for_document(self, document, chunks, section_rows, owner_id=None):
        self.written = [list(c.meta.substance_ids) for c in chunks]
        return []


def _chunk(ordinal: int, stale_ids: list[int]) -> Chunk:
    meta = ChunkMeta(doc_type="msds", source_url="https://example.test/24")
    meta.substance_ids = list(stale_ids)
    return Chunk(
        ordinal=ordinal,
        text=f"chunk {ordinal}",
        token_count=2,
        start_offset=ordinal * 10,
        end_offset=ordinal * 10 + 5,
        section_ordinal=None,
        meta=meta,
    )


def _service(documents: _Documents, resolved, chunks: _Chunks, n_chunks: int = 16):
    ctx = SimpleNamespace(
        extracted=ExtractedText(text="본문", extractor="fake"),
        structured=StructuredDoc(DocType.MSDS, [], StructureStatus.STRUCTURED),
        chunks=[_chunk(i, stale_ids=[999]) for i in range(n_chunks)],
        stored_path=None,
    )
    service = object.__new__(IndexingService)
    service._documents = documents
    service._chunks = chunks
    service._runner = SimpleNamespace(run=lambda *a, **k: ctx)
    service._embedder = None  # no chunk rows come back, so it is never asked
    service._project_substance = lambda raw: None
    service._resolve_substances = lambda *a: list(resolved)
    service.synonym_links = []
    service._register_msds_synonyms = (
        lambda document, doc_type, links, c, owner_id: service.synonym_links.append(links)
    )
    return service


def _raw() -> RawDocument:
    ref = SourceRef(source_id="msds", external_id="24", url="https://example.test/24")
    return RawDocument(ref=ref, content=b"%PDF-", media_type="application/pdf")


def _process(service):
    return service.process(_raw(), DocType.MSDS, source_pk=None)


class TestEmptyResolutionKeepsLinks:
    """(a) - the D13 shape. The links survive and the chunks say so."""

    def test_links_are_not_deleted(self):
        documents = _Documents({43: "subject"})
        _process(_service(documents, [], _Chunks()))
        assert documents.linked == {43: "subject"}
        assert documents.link_calls == 0

    def test_chunks_carry_the_kept_links(self):
        documents, chunks = _Documents({43: "subject"}), _Chunks()
        _process(_service(documents, [], chunks))
        assert chunks.written == [[43]] * 16
        assert all(ids == sorted(documents.linked) for ids in chunks.written)

    def test_nothing_linked_stays_nothing(self):
        documents, chunks = _Documents({}), _Chunks()
        outcome = _process(_service(documents, [], chunks))
        assert chunks.written == [[]] * 16
        assert outcome.substance_links_kept == []


class TestFoundLinksReplace:
    """(b) - a resolution that finds anything is the new truth (BR-37)."""

    def test_both_records_move_together(self):
        documents, chunks = _Documents({43: "subject"}), _Chunks()
        resolved = [(7, SubstanceRelation.SUBJECT), (12, SubstanceRelation.MENTIONED)]
        outcome = _process(_service(documents, resolved, chunks))
        assert documents.linked == {7: "subject", 12: "mentioned"}
        assert chunks.written == [[7, 12]] * 16
        assert outcome.substance_links_kept == []

    def test_duplicates_collapse_the_same_way_in_both(self):
        documents, chunks = _Documents({}), _Chunks()
        resolved = [(43, SubstanceRelation.SUBJECT), (43, SubstanceRelation.MENTIONED)]
        _process(_service(documents, resolved, chunks))
        assert documents.linked == {43: "subject"}
        assert chunks.written == [[43]] * 16

    def test_stale_chunk_ids_never_leak_through(self):
        """The fake chunks start with 999; whatever was on them before is overwritten."""
        documents, chunks = _Documents({}), _Chunks()
        _process(_service(documents, [(5, SubstanceRelation.SUBJECT)], chunks))
        assert all(999 not in ids for ids in chunks.written)


class TestKeptLinksAreSurfaced:
    """(c) - keeping is the safe choice only if somebody finds out."""

    def test_warning_names_the_document_and_the_kept_ids(self, caplog):
        documents = _Documents({43: "subject"})
        with caplog.at_level(logging.WARNING, logger="app.services.indexing_service"):
            _process(_service(documents, [], _Chunks()))
        records = [r for r in caplog.records if r.msg == "substance_links_kept_unresolved"]
        assert len(records) == 1
        assert records[0].document_id == DOC_ID
        assert records[0].kept_substance_ids == [43]

    def test_outcome_reports_it(self):
        outcome = _process(_service(_Documents({43: "subject"}), [], _Chunks()))
        assert outcome.substance_links_kept == [43]

    def test_no_warning_when_resolution_found_links(self, caplog):
        documents = _Documents({43: "subject"})
        with caplog.at_level(logging.WARNING, logger="app.services.indexing_service"):
            _process(_service(documents, [(43, SubstanceRelation.SUBJECT)], _Chunks()))
        assert not [r for r in caplog.records if r.msg == "substance_links_kept_unresolved"]

    def test_reindex_job_summary_lists_the_document(self, monkeypatch):
        import app.db.engine as engine
        import app.jobs.tracker as tracker_module
        from app.services import indexing_service as module

        class _Tracker:
            def __init__(self, *a, **k) -> None:
                pass

            def start(self, job_id) -> None:
                pass

            def add_items(self, job_id, items) -> None:
                pass

            def mark_succeeded(self, *a) -> None:
                pass

            def finalize(self, job_id):
                return SimpleNamespace(value="succeeded")

        class _Scope:
            def __enter__(self):
                return object()

            def __exit__(self, *exc) -> bool:
                return False

        outcomes = {
            1: module.IndexOutcome(1, 3, "structured", True),
            24: module.IndexOutcome(24, 16, "structured", True, substance_links_kept=[43]),
        }

        class _PerDocument:
            def __init__(self, session, settings) -> None:
                pass

            def reindex_document(self, document_id):
                return outcomes[document_id]

        monkeypatch.setattr(tracker_module, "JobTracker", _Tracker)
        monkeypatch.setattr(engine, "session_scope", lambda: _Scope())
        monkeypatch.setattr(module, "IndexingService", _PerDocument)

        runner = object.__new__(IndexingService)
        runner._jobs = None
        runner._s = SimpleNamespace(commit=lambda: None)
        runner._settings = None
        runner._reindexer = SimpleNamespace(documents_to_reindex=lambda scope: [1, 24])
        summary = IndexingService.reindex_job(runner, job_id=9)
        assert summary["substance_links_kept"] == [24]
        assert summary["succeeded"] == 2


@pytest.mark.parametrize(
    ("before", "resolved", "expected"),
    [
        ({43: "subject"}, [], [43]),
        ({43: "subject", 50: "mentioned"}, [], [43, 50]),
        ({43: "subject"}, [(43, SubstanceRelation.SUBJECT)], [43]),
        ({43: "subject"}, [(8, SubstanceRelation.MENTIONED)], [8]),
        ({}, [(8, SubstanceRelation.MENTIONED)], [8]),
        ({}, [], []),
    ],
)
def test_invariant_after_any_reindex(before, resolved, expected):
    """Whatever happened, the written chunks equal the table afterwards."""
    documents, chunks = _Documents(before), _Chunks()
    _process(_service(documents, resolved, chunks, n_chunks=3))
    assert sorted(documents.linked) == expected
    assert chunks.written == [expected] * 3
