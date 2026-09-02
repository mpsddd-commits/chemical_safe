"""BR-65a against the live corpus - name queries reach substance records.

u4 measured the asymmetry this exists to close: CAS queries 3/3, substance-name
queries 0/5, on the same records. The cause is structural - a substance
record's chunks never contain the substance's name (the 황산 inhale chunk
reads "·심각한 기도 자극..."), so text and vector search cannot connect the
name to the chunk. Only `chunk.meta['cas_number']` can, and until BR-65a the
resolved name was never turned into one.

Keyword route only - no embedding model is loaded, so these run in seconds.
The full-pipeline effect (fusion, spread, the golden set) is measured with
`evaluate --retrieval-only`, not asserted here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from sqlalchemy import select

from app.core.types import Scope
from app.db.engine import session_scope
from app.db.models import ChunkRow, SubstanceSynonym
from app.rag.entities import EntityExtractor
from app.rag.retrieval.retrievers import Retrievers

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[2]


def _keyword_hits(query: str, min_score: float = 0.0) -> list[dict]:
    with session_scope() as session:
        intent = EntityExtractor(session).extract(query)
        result = Retrievers(session, embedder=None).keyword(
            query, intent, Scope.public()
        )
        assert not result.failed
        wanted = [c.chunk_id for c in result.candidates if c.score >= min_score]
        rows = session.execute(
            select(ChunkRow.meta).where(ChunkRow.id.in_(wanted))
        ).all()
        return [row[0] for row in rows]


class TestNameQueriesReachSubstanceRecords:
    """The five u4 questions that measured 0.000, by their query shapes."""

    @pytest.mark.parametrize(
        ("query", "cas"),
        [
            ("황산 증기를 흡입하면 어떤 증상이 나타나나요?", "7664-93-9"),
            ("암모니아가 눈에 들어가면 어떤 손상이 생기나요?", "7664-41-7"),
            ("염소에 노출되면 나타나는 일반적인 증상은 무엇인가요?", "7782-50-5"),
            # sub-05's shape: the alias, not the canonical name (BR-65a).
            ("메탄올을 흡입하면 시각에 어떤 영향이 있나요?", "67-56-1"),
        ],
    )
    def test_the_substance_record_is_in_the_keyword_candidates(self, query, cas):
        metas = _keyword_hits(query)
        assert any(m.get("cas_number") == cas for m in metas), (
            f"{query!r} 의 키워드 후보에 CAS {cas} 청크가 없다"
        )

    def test_a_query_naming_nothing_resolves_nothing(self):
        """No substance name, no CAS lookup - plain text search only."""
        with session_scope() as session:
            retrievers = Retrievers(session, embedder=None)
            assert retrievers._cas_for_names([]) == ()


class TestTheAliasFileIsHonest:
    def test_every_canonical_exists_in_the_master(self):
        """The file's own rule: an alias whose canonical the master does not
        carry is a silent no-op, and a silent no-op in a curated file is a lie
        waiting to be believed."""
        raw = yaml.safe_load(
            (ROOT / "config" / "query_aliases.yaml").read_text(encoding="utf-8")
        )
        aliases = raw.get("aliases") or {}
        assert aliases, "별칭 파일이 비어 있다"
        with session_scope() as session:
            known = set(session.scalars(select(SubstanceSynonym.term)))
        missing = [c for c in aliases.values() if c not in known]
        assert not missing, f"마스터에 없는 정식 명칭: {missing}"


class TestTopicSectionsReachTheMsds:
    def test_a_storage_question_lifts_the_storage_section(self):
        """msds-02's shape: the name resolves, the topic word picks section 7,
        and the lift lands on a storage chunk instead of an arbitrary one."""
        metas = _keyword_hits("황산은 어떻게 저장해야 하나요?", min_score=1.0)
        lifted = [m for m in metas if m.get("cas_number") == "7664-93-9"]
        assert any(m.get("section_code") == "msds_07" for m in lifted), [
            m.get("section_code") for m in lifted
        ]

    def test_no_topic_lifts_no_junk(self):
        """A question naming only the substance must not LIFT 법적규제 or
        참고사항 - the arbitrary tie-break this map replaced. The lift is the
        exact-match score; those sections may still arrive as ordinary text
        hits (they contain "황산"), which is fine and is what this test's
        first version wrongly flagged."""
        metas = _keyword_hits("황산이 포함된 자료를 알려주세요", min_score=1.0)
        lifted = [m for m in metas if m.get("cas_number") == "7664-93-9"]
        junk = {"msds_15", "msds_16", "msds_12"}
        assert not any(m.get("section_code") in junk for m in lifted), [
            m.get("section_code") for m in lifted
        ]
