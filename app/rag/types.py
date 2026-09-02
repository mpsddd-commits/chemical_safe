"""Value objects V1~V4 - alive for one request, never persisted.

The persisted shapes live in `db/models.py`. Keeping these separate matters
because they answer different questions: the ORM rows record what an answer
*was*, these carry what the pipeline is *doing*, and conflating them is how a
transient scoring detail ends up in a citation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.types import DocType


@dataclass
class QueryIntent:
    """V1 - what C30 extracted from the question (FR-17).

    `doc_type_hint` is a *weight*, never a filter (BR-66). As a filter, a
    slightly-off question drops the correct document out of the candidate set
    entirely, and the user has no way to tell that happened.
    """

    substance_names: list[str] = field(default_factory=list)
    cas_numbers: list[str] = field(default_factory=list)
    un_numbers: list[str] = field(default_factory=list)
    doc_type_hint: DocType | None = None
    raw_terms: list[str] = field(default_factory=list)

    @property
    def resolved_by_rules(self) -> bool:
        """BR-64 - when rules found something, no LLM call is needed."""
        return bool(self.cas_numbers or self.un_numbers or self.substance_names)


@dataclass
class RetrievalCandidate:
    """V2 - a chunk in flight through fusion and reranking.

    Named to avoid clashing with u1's `core.types.Candidate`, which is a much
    smaller thing (a chunk id and one route's score).
    """

    chunk_id: int
    document_id: int
    doc_type: DocType
    keyword_rank: int | None = None
    vector_rank: int | None = None
    fused_score: float = 0.0
    rerank_score: float | None = None
    # The routes' own scores, carried through fusion. RRF discards them for
    # *ordering* (by design - ranks need no normalisation, BR-68), but the
    # refusal decision needs an actual relevance measure and RRF is not one.
    keyword_score: float | None = None
    vector_score: float | None = None

    @property
    def score(self) -> float:
        """Whatever ordering is currently authoritative."""
        return self.rerank_score if self.rerank_score is not None else self.fused_score

    @property
    def exact_identifier(self) -> bool:
        """A CAS or UN number matched exactly (BR-38).

        The strongest signal this system has: the user typed an identifier and a
        chunk carries it. Cosine similarity says nothing useful about that -
        "CAS 75-31-0 물질에 노출되면" embeds nowhere near a substance record -
        so relevance must not be allowed to overrule it.
        """
        from app.indexing.keyword_index import EXACT_MATCH_SCORE

        return (self.keyword_score or 0.0) >= EXACT_MATCH_SCORE

    @property
    def relevance(self) -> float | None:
        """Cosine similarity, for the refusal threshold (BR-73).

        Measured on the real corpus: on-topic queries top out at 0.66-0.71 and
        off-topic ones at ~0.42, so this separates them. A fused RRF score
        cannot - it is built from rank positions, so the top result of a query
        with no relevant documents scores exactly the same as the top result of
        a good one.
        """
        return self.vector_score


@dataclass
class Evidence:
    """V3 - a final candidate, resolved to the text the model will see.

    `section_code` is `str | None` and callers must handle None. It is not an
    error case: BR-20a demotions and BR-31a merged records genuinely have no
    section label, and inventing one would be a lie about where the text came
    from (BR-90, NFR-8).
    """

    chunk_id: int
    document_id: int
    source_url: str
    document_title: str | None
    section_code: str | None
    section_title: str | None
    text: str
    start_offset: int
    end_offset: int
    score: float
    doc_type: DocType
    # Cosine similarity of this chunk to the query, when the vector route found
    # it. `score` is the ordering position; this is the relevance measure the
    # stage-one refusal reads (BR-73). None means keyword-only, and a
    # keyword-only hit is judged on its own scale rather than treated as 0.
    relevance: float | None = None
    # BR-38 - an exact CAS/UN hit. Kept on the evidence because the refusal gate
    # needs it and cosine similarity cannot express it.
    exact_identifier: bool = False
    # SP-4/SP-5 - surfaced to the prompt as an attribute, never used to exclude.
    suspected_injection: bool = False


@dataclass
class AnswerSentence:
    """One sentence of V4, after ID validation."""

    text: str
    chunk_ids: list[int]


@dataclass
class GeneratedAnswer:
    """V4 - the structured output contract (BR-79, FQ2-11).

    The schema is the reason grounding verification can be deterministic (DD-8),
    and it doubles as the strongest injection defence we have: an instruction
    that hijacks the model still cannot produce anything outside this shape.
    """

    sentences: list[AnswerSentence] = field(default_factory=list)

    @staticmethod
    def json_schema() -> dict:
        return {
            "type": "object",
            "properties": {
                "sentences": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "chunk_ids": {
                                "type": "array",
                                "items": {"type": "integer"},
                            },
                        },
                        "required": ["text", "chunk_ids"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["sentences"],
            "additionalProperties": False,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> GeneratedAnswer:
        sentences = []
        for item in payload.get("sentences") or []:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            raw_ids = item.get("chunk_ids") or []
            # Ids arrive from a model, so they are not yet trustworthy - this
            # only drops the unparseable ones. The whitelist check against what
            # was actually sent happens in the generator (SP-8, BR-81).
            ids = [
                int(i)
                for i in raw_ids
                if isinstance(i, int | str) and str(i).lstrip("-").isdigit()
            ]
            sentences.append(AnswerSentence(text=text, chunk_ids=ids))
        return cls(sentences=sentences)
