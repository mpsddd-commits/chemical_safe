"""Shared, technology-neutral types (component-methods.md section 0)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class DocType(StrEnum):
    MSDS = "msds"
    LAW = "law"
    INCIDENT = "incident"
    USER_UPLOAD = "user_upload"  # u5 — declared here so schema never changes (DD-21)
    # 2026-08-30. The substance API returns one row per substance keyed by route
    # of exposure; a vendor MSDS is a 16-section datasheet. They were both `msds`
    # and the code worked around it in two places - `structure()` fell through to
    # the substance structurer, and `_has_msds` told them apart by section prefix.
    #
    # Retrieval could not. BR-69 lifts one candidate per *missing type* into the
    # cut, so when a chlorine MSDS filled all twenty fused candidates there was
    # nothing to lift and the substance record's `substance_inhale` was left at
    # rank 7 - measured, that is exactly how sub-07 went from Recall 1.0 to 0.0
    # when the MSDS was added.
    SUBSTANCE = "substance"


class StructureStatus(StrEnum):
    STRUCTURED = "structured"
    UNSTRUCTURED = "unstructured"  # FQ-3=A section detection fell back


class SourceKind(StrEnum):
    API = "api"
    PDF = "pdf"
    DATASET = "dataset"


class PolicyDecision(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class JobKind(StrEnum):
    INGEST = "ingest"
    INDEX = "index"
    REINDEX = "reindex"
    UPLOAD_INDEX = "upload_index"  # u5


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class ItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"


class Role(StrEnum):
    """What an account is allowed to reach - B3.

    Two values and no hierarchy: there is one privileged screen group, so a rank
    ordering would be a structure with nothing to order. `ADMIN` is granted by
    `safeenv grant-admin`, never by registering.
    """

    USER = "user"
    ADMIN = "admin"


class SynonymType(StrEnum):
    KO = "ko"
    EN = "en"
    ALIAS = "alias"
    CAS = "cas"
    UN = "un"


class SubstanceRelation(StrEnum):
    SUBJECT = "subject"
    MENTIONED = "mentioned"
    REGULATED = "regulated"


class PipelineStage(StrEnum):
    """Stage boundaries double as resume points (DD-3, BR-44)."""

    FETCH = "fetch"
    EXTRACT = "extract"
    NORMALIZE = "normalize"
    STRUCTURE = "structure"
    CHUNK = "chunk"
    EMBED = "embed"
    PERSIST = "persist"


class RetrievalMode(StrEnum):
    """u2 — how the final candidate order was produced (E14)."""

    HYBRID = "hybrid"
    HYBRID_RERANKED = "hybrid_reranked"


class AnswerOutcome(StrEnum):
    """u2 — the terminal state of one query (E14)."""

    ANSWERED = "answered"
    ANSWERED_PARTIAL = "answered_partial"  # some sentences removed (FQ2-9)
    REFUSED_LOW_RELEVANCE = "refused_low_relevance"
    REFUSED_UNSUPPORTED = "refused_unsupported"
    ERROR = "error"


class RefusalReason(StrEnum):
    NO_CANDIDATES = "no_candidates"
    BELOW_THRESHOLD = "below_threshold"
    # BR-73a - every candidate is a document *about one substance*, and the
    # question named none we carry. Answering would attribute one substance's
    # data to another (2026-09-02).
    UNKNOWN_SUBJECT = "unknown_subject"
    ALL_SENTENCES_UNSUPPORTED = "all_sentences_unsupported"
    # C15 - every filtered sentence was `unverified_by_quota`, so nothing was
    # judged at all. `all_sentences_unsupported` names a verdict this run never
    # reached, and `verifier.py` already says the two must not be shown as one
    # ("we judged it and it failed" vs "we never got to ask") - until 2026-09-08
    # the stored reason made them one anyway. Measured on baseline 609: msds-03
    # refused with a single quota-blocked sentence whose text
    # ("톨루엔의 국내 노출기준은 TWA 50 ppm, STEL 150 ppm입니다") was correct, and it
    # was counted into the 0.120 false-refusal rate that should have been 0.080.
    VERIFICATION_UNAVAILABLE = "verification_unavailable"
    PROVIDER_REFUSAL = "provider_refusal"  # stop_reason == "refusal" (BR-77)


class SupportVerdict(StrEnum):
    """BR-87 — `unverified` is not a third outcome, it is an honest label.

    A sentence we failed to check and a sentence we checked and passed are not
    the same thing, and in safety information collapsing them is dangerous
    (R-6). Both are removed; only one of them is recorded as verified.
    """

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"


class LlmPurpose(StrEnum):
    """E18 — separated so `verify` cost cannot hide inside `answer` (BR-86a)."""

    ANSWER = "answer"
    VERIFY = "verify"
    ENTITY = "entity"
    # u4. Separated for the same reason as `verify`: the judge runs on its own
    # model with its own daily quota, and folding its cost into `answer` would
    # hide the one number the evaluation unit is budgeted against.
    JUDGE = "judge"


class MatchKind(StrEnum):
    """u3 - what a substance lookup matched on (FR-26, BR-101).

    `UN` and `ALIAS` are kept even though no data populates them today. Removing
    them would make two of FR-26's five key types look like they were never
    required; leaving them in shows "five asked for, three working", and they
    start working the moment data arrives (BR-110, DD-21).
    """

    CAS = "cas"
    UN = "un"  # no data: `un_number` is absent from the source (BR-109)
    NAME_KO = "name_ko"
    NAME_EN = "name_en"
    ALIAS = "alias"  # no data: the source carries no synonyms (BR-99)


class CardItemKey(StrEnum):
    """u3 - FR-24's seven items, in the order a card always shows them.

    Fixed order because a card that reorders itself between lookups reads as
    "something changed", and because dropping empty items would let a gap slip
    past unnoticed (BR-102).
    """

    GHS = "ghs"
    HP_CODES = "hp_codes"
    PHYSICAL = "physical"
    PPE = "ppe"
    FIRST_AID = "first_aid"
    STORAGE = "storage"
    REGULATIONS = "regulations"


class ValueOrigin(StrEnum):
    """u3 - where a card value came from. Several may back one item (BR-103)."""

    MSDS = "msds"
    SUBSTANCE_API = "substance_api"
    LAW = "law"


class ExposureRoute(StrEnum):
    """u3 - first-aid sub-items (BR-103, FQ4-7).

    The only broad data this unit has: 40/40 records carry inhale, skin and eye;
    39/40 carry oral. Kept separate rather than merged because in an incident
    what matters is *which route* was exposed.
    """

    INHALE = "inhale"
    SKIN = "skin"
    EYE = "eye"
    ORAL = "oral"


@dataclass(frozen=True)
class SourceRef:
    """Identifies one collectable document at a source."""

    source_id: str
    external_id: str
    url: str
    published_at: datetime | None = None
    revised_at: datetime | None = None
    content_hash: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def ref_key(self) -> str:
        return f"{self.source_id}:{self.external_id}"


@dataclass
class RawDocument:
    ref: SourceRef
    content: bytes | None = None
    payload: dict[str, Any] | None = None
    media_type: str = "application/octet-stream"
    stored_path: str | None = None


@dataclass
class ExtractedText:
    """Normalized text. Every offset in the system is relative to `text` (FQ-5=A)."""

    text: str
    extractor: str

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass
class Section:
    ordinal: int
    section_code: str | None
    section_title: str | None
    start_offset: int
    end_offset: int


@dataclass
class StructuredDoc:
    doc_type: DocType
    sections: list[Section]
    structure_status: StructureStatus


@dataclass
class ChunkMeta:
    """Denormalized copy carried on every chunk (BR-35, BR-36)."""

    doc_type: str
    source_url: str
    published_at: str | None = None
    section_code: str | None = None
    section_title: str | None = None
    substance_ids: list[int] = field(default_factory=list)
    substance_names: list[str] = field(default_factory=list)
    cas_number: str | None = None
    un_number: str | None = None
    law_name: str | None = None
    clause_numbers: list[str] = field(default_factory=list)
    structure_status: str = StructureStatus.STRUCTURED.value
    # u2 / SP-4. Set at index time, surfaced to the prompt as an attribute, and
    # never used to exclude a chunk (SP-5). Declared explicitly rather than
    # tucked into `extra`, which `to_dict` deliberately does not persist.
    suspected_injection: bool = False
    injection_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_type": self.doc_type,
            "source_url": self.source_url,
            "published_at": self.published_at,
            "section_code": self.section_code,
            "section_title": self.section_title,
            "substance_ids": self.substance_ids,
            "substance_names": self.substance_names,
            "cas_number": self.cas_number,
            "un_number": self.un_number,
            "law_name": self.law_name,
            "clause_numbers": self.clause_numbers,
            "structure_status": self.structure_status,
            "suspected_injection": self.suspected_injection,
            "injection_signals": self.injection_signals,
        }


@dataclass
class Chunk:
    ordinal: int
    text: str
    token_count: int
    start_offset: int
    end_offset: int
    section_ordinal: int | None
    meta: ChunkMeta


@dataclass(frozen=True)
class Scope:
    """Search scope. A REQUIRED argument on every search method (DD-19).

    In u1 the only scope in existence is the public corpus. It is modelled now so
    that u5 can introduce owner isolation without changing any signature.
    """

    owner_id: int | None = None

    @classmethod
    def public(cls) -> Scope:
        return cls(owner_id=None)


@dataclass
class Candidate:
    chunk_id: int
    score: float
    route: str  # "keyword" | "vector"


@dataclass
class JobProgress:
    job_id: int
    status: JobStatus
    total_count: int
    success_count: int
    skipped_count: int
    failure_count: int

    @property
    def ratio(self) -> float:
        """BR-50 — zero total renders as 0%."""
        if self.total_count == 0:
            return 0.0
        done = self.success_count + self.skipped_count + self.failure_count
        return min(done / self.total_count, 1.0)
