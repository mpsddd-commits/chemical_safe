"""C3 - a document BR-31a folded still reaches its card (BR-31a <-> BR-104).

The record is 4-tert-뷰틸벤조산 (CAS 98-73-7, `ncis_substance` 30), the one card
in 49 that came back empty although its document had seven sections with
content. It runs through the real extract -> normalize -> structure -> chunk
path here, so the fold is the chunker's own verdict and not an assumption.

The expected card text is built from the *record fields*, not from the section
offsets. An offset applied to the wrong text, or off by one character at
either end of a section, puts a neighbouring field's characters into the value
and fails the equality.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.core.types import (
    CardItemKey,
    ChunkMeta,
    DocType,
    ExposureRoute,
    MatchKind,
    StructuredDoc,
)
from app.processing.chunker import chunk_document
from app.processing.stages.extract import _flatten
from app.processing.stages.normalize import normalize
from app.processing.structure import substance as substance_structure
from app.substances.card import SubstanceCardBuilder
from app.substances.types import SubstanceRef

# data/originals/ncis_substance/30.json, verbatim.
RECORD = {
    "external_id": "30",
    "name_en": "·4-tert-Butylbenzoic acid",
    "name_ko": "·4-tert-뷰틸벤조산",
    "cas_number": "98-73-7",
    "symptom": "·자료없음",
    "inhale": "·기도 자극을 일으킬 수 있음\n·이 물질의 독성학적 특성은 완전히 조사되지 않음\n"
    "·흡입시 유해함",
    "skin": "·피부 자극을 일으킬 수 있음",
    "eyeball": "·눈 자극을 일으킬 수 있음",
    "oral": "·삼켰을 경우 위해함\n·삼켰을 경우 소화관에 자극을 줄 수 있음\n"
    "·독성학적 성질에 대해서는 충분히 연구되지 않았음\n·중추신경계 장애를 일으킬 수 있음\n"
    "·사고로 섭취한 경우는 위해함; 동물 실험 결과 150g 미만의 섭취는 치명적이거나 "
    "건강에 매우 심한 손상을 주었음",
    "etc": "·자료없음",
}

DOC_ID = 69
TITLE = "4-tert-뷰틸벤조산 (4-tert-Butylbenzoic acid) · CAS 98-73-7"
URL = "https://www.data.go.kr/data/15072442/openapi.do#dataNo=30"


class FakeSession:
    """Answers `execute(...).all()` from a queue and counts the queries."""

    def __init__(self, *results: list) -> None:
        self._results = list(results)
        self.calls = 0

    def execute(self, _stmt):
        self.calls += 1
        rows = self._results.pop(0)
        return SimpleNamespace(all=lambda: rows)


def _indexed():
    text = normalize("\n".join(_flatten(RECORD)))
    sections, status = substance_structure.find_sections(text)
    doc = StructuredDoc(doc_type=DocType.SUBSTANCE, sections=sections, structure_status=status)
    meta = ChunkMeta(doc_type=DocType.SUBSTANCE.value, source_url=URL)
    return text, sections, chunk_document(text, doc, meta)


def _chunk_row(body: str, section_id, section_code=None, doc_id=DOC_ID, doc_type="substance"):
    return SimpleNamespace(
        text=body, id=doc_id, title=TITLE, source_url=URL, doc_type=doc_type,
        section_code=section_code, section_title=None, relation="subject",
        section_id=section_id,
    )


def _section_query_row(text: str, section) -> SimpleNamespace:
    return SimpleNamespace(
        full_text=text, start_offset=section.start_offset, end_offset=section.end_offset,
        id=DOC_ID, title=TITLE, source_url=URL, doc_type="substance",
        section_code=section.section_code, section_title=section.section_title,
        relation="subject",
    )


def _ref() -> SubstanceRef:
    return SubstanceRef(
        substance_id=30, cas_number="98-73-7", name_ko="4-tert-뷰틸벤조산",
        name_en=None, matched_on=list(MatchKind)[0],
    )


def _first_aid(card):
    return next(item for item in card.items if item.key is CardItemKey.FIRST_AID).values


class TestFoldedDocument:
    def test_the_record_really_folds(self):
        _text, sections, chunks = _indexed()
        assert len(sections) == 7
        assert len(chunks) == 1 and chunks[0].section_ordinal is None

    def test_each_route_gets_exactly_its_own_field(self):
        text, sections, chunks = _indexed()
        session = FakeSession(
            [_chunk_row(chunks[0].text, None)],
            [_section_query_row(text, s) for s in sections],
        )
        card = SubstanceCardBuilder(session).build(_ref())

        by_route = {value.route: value for value in _first_aid(card)}
        assert {route: value.text for route, value in by_route.items()} == {
            ExposureRoute.INHALE: "inhale: " + RECORD["inhale"],
            ExposureRoute.SKIN: "skin: " + RECORD["skin"],
            ExposureRoute.EYE: "eyeball: " + RECORD["eyeball"],
            ExposureRoute.ORAL: "oral: " + RECORD["oral"],
        }

    def test_values_carry_the_same_source_as_a_chunk_row(self):
        text, sections, chunks = _indexed()
        session = FakeSession(
            [_chunk_row(chunks[0].text, None)],
            [_section_query_row(text, s) for s in sections],
        )
        for value in _first_aid(SubstanceCardBuilder(session).build(_ref())):
            assert (value.document_id, value.document_title, value.source_url) == (
                DOC_ID, TITLE, URL,
            )
            assert value.section_code in {
                "substance_inhale", "substance_skin", "substance_eye", "substance_oral",
            }
            assert value.section_title


class TestReplacedNotAdded:
    def test_folded_chunks_give_way_to_the_sections_once(self):
        """A law document is read whole into 적용 법령, so a leftover folded
        chunk or a second copy of the sections would show up there."""
        text = "제1조 목적\n제2조 정의"
        chunks = [
            _chunk_row("제1조 목적", section_id=None, doc_type="law"),
            _chunk_row("제2조 정의", section_id=None, doc_type="law"),
        ]
        sections = [
            SimpleNamespace(start_offset=0, end_offset=6, section_code="law_1",
                            section_title="제1조"),
            SimpleNamespace(start_offset=6, end_offset=len(text), section_code="law_2",
                            section_title="제2조"),
        ]
        rows = [_section_query_row(text, s) for s in sections]
        for row in rows:
            row.doc_type = "law"
        card = SubstanceCardBuilder(FakeSession(chunks, rows)).build(_ref())

        regulations = next(i for i in card.items if i.key is CardItemKey.REGULATIONS).values
        assert [(v.text, v.section_code) for v in regulations] == [
            ("제1조 목적", "law_1"), ("제2조 정의", "law_2"),
        ]


class TestNotFolded:
    def test_a_sectioned_document_is_never_read_twice(self):
        rows = [
            _chunk_row("inhale: 흡입 본문", section_id=11, section_code="substance_inhale"),
            _chunk_row("skin: 피부 본문", section_id=12, section_code="substance_skin"),
        ]
        session = FakeSession(rows)
        card = SubstanceCardBuilder(session).build(_ref())

        assert session.calls == 1  # the section query never ran
        assert [v.text for v in _first_aid(card)] == ["inhale: 흡입 본문", "skin: 피부 본문"]

    def test_one_sectioned_chunk_is_enough_to_skip_the_fallback(self):
        rows = [
            _chunk_row("inhale: 흡입 본문", section_id=11, section_code="substance_inhale"),
            _chunk_row("머리말", section_id=None),
        ]
        session = FakeSession(rows)
        SubstanceCardBuilder(session).build(_ref())
        assert session.calls == 1

    def test_a_document_without_sections_creates_nothing(self):
        law = _chunk_row("제1조 목적", section_id=None, doc_id=7, doc_type="law")
        session = FakeSession([law], [])
        card = SubstanceCardBuilder(session).build(_ref())

        assert session.calls == 2
        assert _first_aid(card) == []
        regulations = next(i for i in card.items if i.key is CardItemKey.REGULATIONS).values
        assert [v.text for v in regulations] == ["제1조 목적"]  # its chunk is kept as it was
        assert sum(len(item.values) for item in card.items) == 1
