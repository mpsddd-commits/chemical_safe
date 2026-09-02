"""The substance/MSDS type split — 2026-08-30.

A substance API record and a vendor MSDS were both `doc_type=msds`. The code
already knew they were different and worked around it twice (the structurer fell
through to the substance parser, `_has_msds` told them apart by section prefix);
retrieval could not, because BR-69 lifts one candidate per **missing type** and
there was only ever one type to miss.

Measured: when a chlorine MSDS filled all twenty fused candidates, the substance
record's `substance_inhale` sat at rank 7 and was cut. Relabelling it recovered
Recall@5 from 0.667 to 0.700 with no other question moving.
"""

from __future__ import annotations

import yaml

from app.core.types import DocType
from app.processing.stages.structure import structure

SUBSTANCE_TEXT = """external_id: 4994
name_en: ·Chlorine
name_ko: ·염소
cas_number: 7782-50-5
symptom: ·독성; 흡입하면 치명적일 수 있음
inhale: ·질식과 타는 듯한 느낌, 기도폐쇄
skin: ·피부 화상
eyeball: ·눈 자극 및 손상
oral: ·구토가 일어날 수 있음
etc: ·자료없음
"""


class TestTheTypeExists:
    def test_substance_is_its_own_type(self):
        assert DocType.SUBSTANCE.value == "substance"

    def test_every_type_is_distinct(self):
        values = [t.value for t in DocType]
        assert len(values) == len(set(values))

    def test_the_substance_source_declares_it(self):
        """`config/sources.yaml` is the authority; `retype` reconciles rows to it."""
        from pathlib import Path

        config = yaml.safe_load(
            (Path(__file__).resolve().parents[2] / "config" / "sources.yaml").read_text(
                encoding="utf-8"
            )
        )
        spec = next(s for s in config["sources"] if s["source_id"] == "ncis_substance")
        assert spec["doc_type"] == "substance"

    def test_msds_pdf_still_declares_msds(self):
        """The split must not have moved the vendor datasheets with it."""
        from pathlib import Path

        config = yaml.safe_load(
            (Path(__file__).resolve().parents[2] / "config" / "sources.yaml").read_text(
                encoding="utf-8"
            )
        )
        spec = next(s for s in config["sources"] if s["source_id"] == "msds_pdf")
        assert spec["doc_type"] == "msds"


class TestStructuring:
    def test_a_substance_record_takes_the_direct_route(self):
        """No longer by way of a failed MSDS parse."""
        result = structure(SUBSTANCE_TEXT, DocType.SUBSTANCE)
        codes = [s.section_code for s in result.sections]
        assert "substance_inhale" in codes
        assert "substance_eye" in codes

    def test_the_upload_fallback_is_kept(self):
        """A user's PDF may be a substance record and we do not get to declare it.

        Collected records take the direct branch; uploads keep the fallback,
        because nobody tells us in advance what someone uploaded.
        """
        result = structure(SUBSTANCE_TEXT, DocType.USER_UPLOAD)
        assert [s.section_code for s in result.sections]

    def test_an_msds_document_is_unaffected(self):
        text = "\n".join(
            [
                "1. 화학제품과 회사에 관한 정보",
                "제품명: 염소",
                "2. 유해성·위험성",
                "위험",
                "3. 구성성분의 명칭 및 함유량",
                "염소 7782-50-5",
                "4. 응급조치 요령",
                "신선한 공기가 있는 곳으로",
                "5. 폭발·화재시 대처방법",
                "분말 소화기",
                "6. 누출 사고시 대처방법",
                "격리",
                "7. 취급 및 저장방법",
                "환기",
                "8. 노출방지 및 개인보호구",
                "보안경",
                "9. 물리화학적 특성",
                "황록색 기체",
            ]
        )
        result = structure(text, DocType.MSDS)
        assert any((s.section_code or "").startswith("msds_") for s in result.sections)


class TestSubstanceLinksStayTheSubject:
    def test_relation_mapping_covers_the_new_type(self):
        """A substance record is *about* its substance, exactly as before.

        Missing this entry would raise a KeyError on the first re-index of a
        substance document - the loudest possible failure, but only at run time.
        """
        from app.core.types import SubstanceRelation
        from app.services.indexing_service import _RELATION_BY_DOC_TYPE

        assert _RELATION_BY_DOC_TYPE[DocType.SUBSTANCE] is SubstanceRelation.SUBJECT

    def test_every_doc_type_has_a_relation(self):
        from app.services.indexing_service import _RELATION_BY_DOC_TYPE

        missing = [t for t in DocType if t not in _RELATION_BY_DOC_TYPE]
        assert not missing, f"doc types with no substance relation: {missing}"


class TestSpreadCanNowSeparateThem:
    def test_a_second_type_is_liftable(self):
        """BR-69 with one type present has nothing to lift - that was the bug."""
        from app.rag.retrieval.fusion import ensure_doc_type_spread
        from app.rag.types import RetrievalCandidate

        def candidate(index: int, doc_type: DocType) -> RetrievalCandidate:
            return RetrievalCandidate(
                chunk_id=index, document_id=1, doc_type=doc_type, fused_score=1.0 / (index + 1)
            )

        # Seven MSDS chunks, then the substance record - the measured shape of
        # sub-07's fused list.
        candidates = [candidate(i, DocType.MSDS) for i in range(7)]
        candidates.append(candidate(7, DocType.SUBSTANCE))

        head = ensure_doc_type_spread(list(candidates), 5)
        assert any(c.doc_type is DocType.SUBSTANCE for c in head)
        assert len(head) == 5

    def test_one_type_only_is_left_alone(self):
        """Nothing to lift is not an error; the head stays as fused."""
        from app.rag.retrieval.fusion import ensure_doc_type_spread
        from app.rag.types import RetrievalCandidate

        candidates = [
            RetrievalCandidate(chunk_id=i, document_id=1, doc_type=DocType.MSDS)
            for i in range(8)
        ]
        head = ensure_doc_type_spread(candidates, 5)
        assert [c.chunk_id for c in head] == [0, 1, 2, 3, 4]
