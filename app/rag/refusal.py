"""C39 - stage-one refusal (BR-73~75, FR-20).

Refusing before the LLM call is the point. A weak-evidence question answered
anyway produces a confident-looking answer with weak citations, which is worse
than no answer in a safety domain (R-6) - and it costs a generation call plus
one verification call per sentence to produce (BR-86a).

A refusal always carries source links (BR-75). "I don't know" with nowhere to go
leaves the user worse off than a search engine would.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings, get_settings
from app.core.types import DocType, RefusalReason
from app.rag.types import Evidence

# Document types that are *about one substance*. A user upload is excluded:
# we do not get to declare what someone uploaded, and refusing their own
# document back at them would be the wrong side of this trade.
_SUBJECT_SCOPED = frozenset({DocType.MSDS, DocType.SUBSTANCE})


@dataclass
class RefusalDecision:
    refused: bool
    reason: RefusalReason | None = None
    links: list[dict] = field(default_factory=list)


def source_links(evidence: list[Evidence]) -> list[dict]:
    """BR-75 - one entry per document, in evidence order.

    Deduplicated by document: five chunks of the same statute are one place to
    go, and listing it five times makes the refusal look like a result set.
    """
    seen: set[int] = set()
    links: list[dict] = []
    for item in evidence:
        if item.document_id in seen:
            continue
        seen.add(item.document_id)
        links.append(
            {
                "document_id": item.document_id,
                "title": item.document_title,
                "section_code": item.section_code,
                "source_url": item.source_url,
            }
        )
    return links


def decide(
    evidence: list[Evidence], settings: Settings | None = None
) -> RefusalDecision:
    """Judge on **relevance**, not on the fused ordering score.

    The first implementation thresholded `score`, which after fusion is an RRF
    value. That cannot work, and the reason is structural rather than a matter
    of calibration: RRF is built from rank positions, so the top result of a
    query with no relevant documents scores exactly what the top result of a
    good query scores. Measured on the real corpus, "오늘 점심 메뉴 추천해줘"
    produced the same fused score as "황산 취급 시 보호구는?".

    Cosine similarity does separate them - on-topic 0.66~0.71, off-topic ~0.42 -
    so that is what the threshold reads.

    A keyword-only candidate has no similarity. It is **not** treated as
    irrelevant: an exact CAS match is the most precise signal a user can give
    (BR-38), and scoring it 0 would refuse the queries this corpus answers best.
    """
    settings = settings or get_settings()

    if not evidence:
        return RefusalDecision(True, RefusalReason.NO_CANDIDATES, [])

    if any(item.exact_identifier for item in evidence):
        # BR-38 - the user typed a CAS or UN number and a chunk carries it.
        # Measured 2026-08-26: "CAS 75-31-0 물질에 노출되면 어떻게 해야 하나요?"
        # found the right record by exact match and was refused at cosine 0.481
        # against a 0.50 threshold. An identifier is a fact, not a fuzzy signal,
        # and a similarity score has no standing to overrule it.
        return RefusalDecision(False)

    # BR-73a - subject-scoped evidence with no subject (2026-09-02).
    #
    # A relevance threshold cannot reach this case, and not by a margin that
    # calibration could close: measured, "벤젠에 노출되면 어떤 응급조치를"
    # scored 0.631 while "황산은 어떻게 저장해야 하나요" - a question this
    # corpus answers - scored 0.627. Any threshold catching the first kills
    # the second. That is defect 27's shape one axis over: the score is
    # measuring topic, and both questions are about the same topic.
    #
    # What differs is the SUBJECT. An MSDS or a substance record is a document
    # about one named substance; 카드뮴 and 벤젠 are in neither the master nor
    # the corpus. Reaching this line means no CAS was typed and no name
    # resolved (the check above returns early when either did), so if every
    # candidate is substance-scoped, the answer would attribute one
    # substance's toxicity or first-aid data to another. In a safety domain
    # that is the worst failure this system can produce (R-6) - worse than
    # silence, because it looks like an answer.
    #
    # Law and incident documents are not scoped this way: "사업주는 물질안전
    # 보건자료를 어떻게 관리해야" names no substance and needs none, and its
    # evidence is statute text. Measured, that question is unaffected.
    # Judged on the BEST candidate, not on all of them. BR-69 lifts one chunk
    # per missing document type into the head, so an `all()` test is defeated
    # by the type-spread rule itself: measured, ref-05 kept its answer because
    # a 제90조 chunk rode the spread into rank 5 while ranks 1-4 were other
    # substances' first-aid sections. The spread candidate is there by
    # construction, not because it answers.
    if evidence and evidence[0].doc_type in _SUBJECT_SCOPED:
        return RefusalDecision(
            True, RefusalReason.UNKNOWN_SUBJECT, source_links(evidence)
        )

    scored = [item.relevance for item in evidence if item.relevance is not None]
    if not scored:
        # Keyword-only results. Nothing to threshold against, and the keyword
        # route only returns rows that actually matched.
        return RefusalDecision(False)

    if max(scored) < settings.refusal_score_threshold:
        # Links still go out: we found *something*, just not enough to answer on.
        return RefusalDecision(True, RefusalReason.BELOW_THRESHOLD, source_links(evidence))

    return RefusalDecision(False)
