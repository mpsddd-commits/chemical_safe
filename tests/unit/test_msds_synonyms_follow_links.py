"""D14 - an MSDS's synonyms follow `document_substance`, not this run's resolution.

D12 stopped an empty resolution from emptying the chunks' `substance_ids`: the
chunks are stamped from the table, and the table keeps its links. The synonym
step still took the resolution. When it came back empty the document looked
like "about no substance" and `replace_document_synonyms` cleared every name it
had printed - D13's defect turned into lost synonyms.

Revised BR-97 says the names belong to "the substance the document is linked
to", and BR-36 makes the table that source. These run `process` with the real
`_register_msds_synonyms` and the real `msds_synonyms.register`, over fake
repositories - no database, no corpus:

(a) an empty resolution with links left keeps the document's synonym rows;
(b) a resolution that finds a new link registers the names on the new link;
(c) the chunks and the synonym step take one and the same link list;
(d) which names are taken is what it was before.

The tempting revert this refuses: "resolution empty, so clear the names".
"""

from __future__ import annotations

from types import SimpleNamespace

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
from app.substances import msds_synonyms as ms

DOC_ID = 728
SILICATE, PROPANAMINE = 16, 1
SUBSTANCES = {
    SILICATE: SimpleNamespace(id=SILICATE, cas_number="78-10-4"),
    PROPANAMINE: SimpleNamespace(id=PROPANAMINE, cas_number="75-31-0"),
}
BASE = {SILICATE: ["에틸 실리케이트"], PROPANAMINE: ["아이소프로필아민"]}
SILICATE_TEXT = "관용명및이명 Tetraethoxysilane\nCAS번호 78-10-4"
PROPANAMINE_TEXT = "관용명및이명 2-Propanamine\nCAS번호 75-31-0"


class _Documents:
    """`document_substance` for one document. Mirrors `DocumentRepo`."""

    def __init__(self, linked: dict[int, str]) -> None:
        self.linked = dict(linked)
        self.link_reads = 0

    def upsert(self, **_kwargs):
        return SimpleNamespace(id=DOC_ID, title=None)

    def set_extracted_text(self, *_args) -> None:
        pass

    def replace_sections(self, *_args):
        return []

    def link_substances(self, document, links) -> None:
        self.linked = {}
        for sid, relation in links:
            self.linked.setdefault(sid, relation.value)

    def substance_links(self, document_id: int) -> list[tuple[int, SubstanceRelation]]:
        assert document_id == DOC_ID
        self.link_reads += 1
        return [(sid, SubstanceRelation(self.linked[sid])) for sid in sorted(self.linked)]

    def single_subject_msds(self, exclude_document_id: int):
        return []


class _Substances:
    """`substance_synonym` rows owned by documents, keyed by owner."""

    def __init__(self, rows: dict[int, list[tuple[int, list]]] | None = None) -> None:
        self.rows = dict(rows or {})

    def get_by_id(self, substance_id: int):
        return SUBSTANCES.get(substance_id)

    def projected_names(self):
        return BASE, {}

    def replace_document_synonyms(self, document_id, entries, *, owned_types):
        assert owned_types == ms.MSDS_SYNONYM_TYPES
        self.rows[document_id] = [(s.id, list(terms)) for s, terms in entries]
        return sum(len(terms) for _s, terms in entries)


class _Chunks:
    def __init__(self) -> None:
        self.written: list[list[int]] = []

    def replace_for_document(self, document, chunks, section_rows, owner_id=None):
        self.written = [list(c.meta.substance_ids) for c in chunks]
        return []


def _chunk(text: str) -> Chunk:
    meta = ChunkMeta(doc_type="msds", source_url="https://example.test/728")
    meta.section_code = ms.COMPOSITION_SECTION
    return Chunk(
        ordinal=0, text=text, token_count=4, start_offset=0, end_offset=len(text),
        section_ordinal=None, meta=meta,
    )


def _process(documents, substances, resolved, text=SILICATE_TEXT, chunks=None):
    chunks = chunks or _Chunks()
    ctx = SimpleNamespace(
        extracted=ExtractedText(text=text, extractor="fake"),
        structured=StructuredDoc(DocType.MSDS, [], StructureStatus.STRUCTURED),
        chunks=[_chunk(text)],
        stored_path=None,
    )
    service = object.__new__(IndexingService)
    service._documents = documents
    service._chunks = chunks
    service._substances = substances
    service._runner = SimpleNamespace(run=lambda *a, **k: ctx)
    service._embedder = None  # no chunk rows come back, so it is never asked
    service._project_substance = lambda raw: None
    service._resolve_substances = lambda *a: list(resolved)
    ref = SourceRef(source_id="msds", external_id="728", url="https://example.test/728")
    raw = RawDocument(ref=ref, content=b"%PDF-", media_type="application/pdf")
    return service.process(raw, DocType.MSDS, source_pk=None), chunks


def _silicate_rows():
    return [(SILICATE, [("Tetraethoxysilane", "tetraethoxysilane", ms.COMMON_NAME)])]


def _names(substances) -> list:
    return substances.rows.get(DOC_ID)


class TestEmptyResolutionKeepsNames:
    """(a) - the D13 shape. The link survives, and so do the names it printed."""

    def test_rows_are_not_cleared(self):
        substances = _Substances({DOC_ID: _silicate_rows()})
        _process(_Documents({SILICATE: "subject"}), substances, resolved=[])
        assert _names(substances) == _silicate_rows()

    def test_kept_names_are_reported_with_the_kept_link(self):
        substances = _Substances({DOC_ID: _silicate_rows()})
        outcome, _ = _process(_Documents({SILICATE: "subject"}), substances, resolved=[])
        assert outcome.substance_links_kept == [SILICATE]
        assert _names(substances)[0][0] in outcome.substance_links_kept

    def test_nothing_linked_still_clears(self):
        """Not linked to anything is still "no subject": its old rows go."""
        substances = _Substances({DOC_ID: _silicate_rows()})
        _process(_Documents({}), substances, resolved=[])
        assert _names(substances) == []

    def test_a_mentioned_link_alone_still_clears(self):
        """Keeping a link does not promote it: only a subject gets names."""
        substances = _Substances({DOC_ID: _silicate_rows()})
        _process(_Documents({SILICATE: "mentioned"}), substances, resolved=[])
        assert _names(substances) == []


class TestFoundLinksMoveTheNames:
    """(b) - a resolution that finds a link is the new truth, for names too."""

    def test_names_register_on_the_new_link(self):
        substances = _Substances({DOC_ID: _silicate_rows()})
        documents = _Documents({SILICATE: "subject"})
        _process(
            documents, substances, resolved=[(PROPANAMINE, SubstanceRelation.SUBJECT)],
            text=PROPANAMINE_TEXT,
        )
        assert documents.linked == {PROPANAMINE: "subject"}
        assert _names(substances) == [
            (PROPANAMINE, [("2-Propanamine", "2-propanamine", ms.COMMON_NAME)])
        ]


class TestOneLinkList:
    """(c) - chunks and synonyms read the table once and share that read."""

    def test_the_table_is_read_once(self):
        documents = _Documents({SILICATE: "subject"})
        _process(documents, _Substances(), resolved=[])
        assert documents.link_reads == 1

    def test_duplicate_resolution_uses_the_tables_relation(self):
        """The table keeps the first relation; the names follow the table, not `links`.

        `(16, mentioned), (16, subject)` settles as `16: mentioned`. The chunks
        say [16]; the synonym step must see "mentioned" too, so no names.
        """
        substances = _Substances({DOC_ID: _silicate_rows()})
        documents = _Documents({})
        _outcome, chunks = _process(
            documents, substances,
            resolved=[
                (SILICATE, SubstanceRelation.MENTIONED),
                (SILICATE, SubstanceRelation.SUBJECT),
            ],
        )
        assert documents.linked == {SILICATE: "mentioned"}
        assert chunks.written == [[SILICATE]]
        assert _names(substances) == []


class TestExtractionUnchanged:
    """(d) - only the subject's source moved; the names taken are the same."""

    def test_ordinary_run_writes_what_register_writes_directly(self):
        substances = _Substances()
        _process(
            _Documents({}), substances, resolved=[(SILICATE, SubstanceRelation.SUBJECT)]
        )

        direct = _Substances()
        current = ms.MsdsDocument(
            document_id=DOC_ID, title=None, substance_id=SILICATE, cas_number="78-10-4",
            extracted_text=SILICATE_TEXT,
            chunks=((SILICATE_TEXT, ms.COMPOSITION_SECTION),),
        )
        ms.register(direct, DOC_ID, current, [], BASE, {})
        assert _names(substances) == _names(direct) == _silicate_rows()

    def test_kept_link_extracts_the_same_names_as_a_found_link(self):
        kept, found = _Substances(), _Substances()
        _process(_Documents({SILICATE: "subject"}), kept, resolved=[])
        _process(
            _Documents({SILICATE: "subject"}), found,
            resolved=[(SILICATE, SubstanceRelation.SUBJECT)],
        )
        assert _names(kept) == _names(found) == _silicate_rows()
