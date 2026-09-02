"""Value objects for u4 - alive for one evaluation run, never persisted.

The persisted shapes are `EvaluationRun` and `EvaluationItem` in `db/models.py`.
Keeping them apart is the same split u2 made between `rag/types.py` and the ORM:
these carry what the run is *doing*, the rows record what it *found*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Expects(StrEnum):
    ANSWER = "answer"
    REFUSAL = "refusal"


class ItemStatus(StrEnum):
    DONE = "done"
    SKIPPED = "skipped"
    QUOTA_EXHAUSTED = "quota_exhausted"
    FAILED = "failed"


class RunStatus(StrEnum):
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunMode(StrEnum):
    RETRIEVAL_ONLY = "retrieval_only"
    FULL = "full"


class Verdict(StrEnum):
    OK = "ok"
    REGRESSION = "regression"
    INCOMPARABLE = "incomparable"
    NO_BASELINE = "no_baseline"


@dataclass(frozen=True)
class EvidenceRef:
    """Where the answer to a golden question lives (BR-112).

    `source` + `external_id`, never a chunk id. This project has re-indexed four
    times; a golden set keyed on chunk ids would have been invalidated four
    times with it. `external_id` is the key BR-09 already uses to decide whether
    a document changed, so it survives re-collection too.

    `section` is None for documents whose sections were folded away by BR-31a -
    13 of them in the corpus, all 12 incidents and one substance record. Those
    are scored at document level (BR-113) rather than inventing a section label.
    """

    source: str
    external_id: str
    section: str | None = None

    @property
    def document_scoped(self) -> bool:
        return self.section is None


@dataclass(frozen=True)
class GoldenQuestion:
    id: str
    category: str
    question: str
    expects: Expects
    answer_points: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    rationale: str | None = None

    @property
    def wants_answer(self) -> bool:
        return self.expects is Expects.ANSWER


@dataclass(frozen=True)
class GoldenSet:
    path: str
    sha256: str
    questions: tuple[GoldenQuestion, ...]

    def __len__(self) -> int:
        return len(self.questions)


@dataclass(frozen=True)
class RetrievedRef:
    """One retrieval candidate, projected onto what scoring compares."""

    rank: int
    chunk_id: int
    document_id: int
    section_code: str | None

    def as_dict(self) -> dict:
        return {
            "rank": self.rank,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "section_code": self.section_code,
        }

    @classmethod
    def from_dict(cls, data: dict) -> RetrievedRef:
        return cls(
            rank=int(data["rank"]),
            chunk_id=int(data["chunk_id"]),
            document_id=int(data["document_id"]),
            section_code=data.get("section_code"),
        )


@dataclass(frozen=True)
class RetrievalScore:
    recall: dict[int, float]
    reciprocal_rank: float
    hits: int
    expected: int


@dataclass(frozen=True)
class Judgement:
    """C47's verdict. Both fields come from **one** call (BR-126)."""

    correct: bool
    faithful: bool
    reason: str

    @staticmethod
    def json_schema() -> dict:
        return {
            "type": "object",
            "properties": {
                "correct": {"type": "boolean"},
                "faithful": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["correct", "faithful", "reason"],
            "additionalProperties": False,
        }


@dataclass
class ItemOutcome:
    """Everything one question produced, before it becomes a row."""

    question_id: str
    category: str
    expects: Expects
    status: ItemStatus
    query_id: int | None = None
    outcome: str | None = None
    retrieved: list[RetrievedRef] = field(default_factory=list)
    recall_at_5: float | None = None
    recall_at_10: float | None = None
    reciprocal_rank: float | None = None
    citation_precision: float | None = None
    refusal_correct: bool | None = None
    judgement: Judgement | None = None
    llm_calls: int = 0
    total_ms: int | None = None
    error_kind: str | None = None


@dataclass(frozen=True)
class MetricDelta:
    name: str
    baseline: float | None
    current: float | None
    tolerance: float
    higher_is_better: bool = True

    @property
    def delta(self) -> float | None:
        if self.baseline is None or self.current is None:
            return None
        return round(self.current - self.baseline, 4)

    @property
    def regressed(self) -> bool:
        d = self.delta
        if d is None:
            return False
        # `tolerance` is an allowed *drop*; for a metric where lower is better
        # (false refusal), the allowed movement is upward instead.
        return (-d if self.higher_is_better else d) > self.tolerance


@dataclass(frozen=True)
class ComparisonReport:
    run_id: int
    baseline_id: int | None
    verdict: Verdict
    deltas: tuple[MetricDelta, ...] = ()
    warnings: tuple[str, ...] = ()
