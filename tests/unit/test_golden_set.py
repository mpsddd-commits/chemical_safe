"""C44 — the golden set is validated before a single question is scored.

A full run costs days of free-tier quota. A typo found on day seven is a week
thrown away, so every check that can happen up front happens up front (BR-114).

These tests exercise the schema half only; the corpus half needs a database and
lives in `tests/integration/test_evaluation.py` (NFR-28).
"""

from __future__ import annotations

import textwrap

import pytest

from app.evaluation.golden_set import GoldenSetError, GoldenSetLoader
from app.evaluation.types import Expects

VALID = """
version: 1
questions:
  - id: law-01
    category: law
    question: 유해화학물질을 함께 보관해도 되나요?
    expects: answer
    answer_points:
      - 혼합 보관 금지
    evidence:
      - source: law_api
        external_id: "000162"
        section: 제13조
  - id: inc-01
    category: incident
    question: 광운대 폭발 사고의 원인은?
    expects: answer
    answer_points:
      - 폐액용기에 아세톤
    evidence:
      - source: incident_data
        external_id: "2025-155"
  - id: ref-01
    category: refusal
    question: 오늘 날씨 어때요?
    expects: refusal
    rationale: 코퍼스 밖
    evidence: []
"""


def _write(tmp_path, text: str):
    path = tmp_path / "golden.yaml"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def _load(tmp_path, text: str):
    # No session: the schema half must not need a database (NFR-28).
    return GoldenSetLoader().load(_write(tmp_path, text))


class TestValidSet:
    def test_parses(self, tmp_path):
        golden = _load(tmp_path, VALID)
        assert len(golden) == 3
        assert [q.id for q in golden.questions] == ["law-01", "inc-01", "ref-01"]

    def test_expects_becomes_an_enum(self, tmp_path):
        golden = _load(tmp_path, VALID)
        assert golden.questions[0].expects is Expects.ANSWER
        assert golden.questions[2].expects is Expects.REFUSAL

    def test_a_sectionless_reference_is_allowed(self, tmp_path):
        """BR-113 — the incident documents genuinely have no sections."""
        golden = _load(tmp_path, VALID)
        assert golden.questions[1].evidence[0].section is None
        assert golden.questions[1].evidence[0].document_scoped

    def test_hash_changes_with_content(self, tmp_path):
        first = _load(tmp_path, VALID).sha256
        second = _load(tmp_path, VALID.replace("오늘 날씨", "내일 날씨")).sha256
        assert first != second

    def test_hash_is_stable_for_identical_content(self, tmp_path):
        assert _load(tmp_path, VALID).sha256 == _load(tmp_path, VALID).sha256


class TestSchemaFailures:
    """Every one of these fails before any question is scored."""

    def test_missing_file(self, tmp_path):
        with pytest.raises(GoldenSetError, match="not found"):
            GoldenSetLoader().load(tmp_path / "nope.yaml")

    def test_no_questions(self, tmp_path):
        with pytest.raises(GoldenSetError, match="no questions"):
            _load(tmp_path, "version: 1\nquestions: []\n")

    def test_duplicate_id(self, tmp_path):
        with pytest.raises(GoldenSetError, match="duplicate"):
            _load(tmp_path, VALID + VALID.split("questions:")[1])

    def test_unknown_category(self, tmp_path):
        with pytest.raises(GoldenSetError, match="unknown category"):
            _load(tmp_path, VALID.replace("category: law", "category: 잡담"))

    def test_bad_expects(self, tmp_path):
        with pytest.raises(GoldenSetError, match="expects"):
            _load(tmp_path, VALID.replace("expects: answer", "expects: maybe", 1))

    def test_answer_question_without_evidence(self, tmp_path):
        broken = """
        version: 1
        questions:
          - id: law-01
            category: law
            question: 질문
            expects: answer
            answer_points: [요지]
            evidence: []
        """
        with pytest.raises(GoldenSetError, match="needs evidence"):
            _load(tmp_path, broken)

    def test_answer_question_without_points(self, tmp_path):
        """Without them the judge has nothing to compare against, and accuracy
        silently degrades into "did it say anything at all"."""
        broken = """
        version: 1
        questions:
          - id: law-01
            category: law
            question: 질문
            expects: answer
            evidence:
              - source: law_api
                external_id: "000162"
                section: 제13조
        """
        with pytest.raises(GoldenSetError, match="answer_points"):
            _load(tmp_path, broken)

    def test_refusal_question_carrying_evidence(self, tmp_path):
        """The author disagreed with themselves; stopping beats guessing."""
        broken = """
        version: 1
        questions:
          - id: ref-01
            category: refusal
            question: 질문
            expects: refusal
            evidence:
              - source: law_api
                external_id: "000162"
        """
        with pytest.raises(GoldenSetError, match="no evidence"):
            _load(tmp_path, broken)

    def test_evidence_without_external_id(self, tmp_path):
        broken = """
        version: 1
        questions:
          - id: law-01
            category: law
            question: 질문
            expects: answer
            answer_points: [요지]
            evidence:
              - source: law_api
        """
        with pytest.raises(GoldenSetError, match="external_id"):
            _load(tmp_path, broken)

    def test_empty_question_text(self, tmp_path):
        with pytest.raises(GoldenSetError, match="empty"):
            _load(tmp_path, VALID.replace("question: 오늘 날씨 어때요?", 'question: ""'))


class TestTheRealGoldenSet:
    """The shipped file must at least parse without a database."""

    def test_repository_golden_set_parses(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "eval" / "golden-set.yaml"
        golden = GoldenSetLoader().load(path)
        assert len(golden) == 30
        answers = [q for q in golden.questions if q.wants_answer]
        assert len(answers) == 25
        assert len(golden.questions) - len(answers) == 5

    def test_every_answer_question_names_its_evidence(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "eval" / "golden-set.yaml"
        for question in GoldenSetLoader().load(path).questions:
            if question.wants_answer:
                assert question.evidence
                assert question.answer_points
