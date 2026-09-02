"""C33 - reciprocal rank fusion and document-type allocation (BR-68, BR-69).

RRF uses ranks, not scores, which is exactly why it fits here: keyword ranking
is `ts_rank` and vector ranking is cosine similarity, and no principled constant
converts one into the other. Ranks are comparable by construction, so nothing
has to be normalised and no tuning constant is invented.
"""

from __future__ import annotations

from collections import defaultdict

from app.core.types import Candidate, DocType
from app.rag.types import RetrievalCandidate


def reciprocal_rank_fusion(
    keyword: list[Candidate],
    vector: list[Candidate],
    *,
    k: int = 60,
    doc_types: dict[int, DocType] | None = None,
    document_ids: dict[int, int] | None = None,
) -> list[RetrievalCandidate]:
    """score(d) = sum over routes of 1 / (k + rank(d))."""
    ranks: dict[int, dict[str, int]] = defaultdict(dict)
    # The routes' raw scores ride along unused by the fusion itself. They are
    # what the refusal threshold needs (BR-73): RRF measures rank, not relevance.
    scores: dict[int, dict[str, float]] = defaultdict(dict)
    for position, candidate in enumerate(keyword, start=1):
        ranks[candidate.chunk_id]["keyword"] = position
        scores[candidate.chunk_id]["keyword"] = candidate.score
    for position, candidate in enumerate(vector, start=1):
        ranks[candidate.chunk_id]["vector"] = position
        scores[candidate.chunk_id]["vector"] = candidate.score

    doc_types = doc_types or {}
    document_ids = document_ids or {}

    fused: list[RetrievalCandidate] = []
    for chunk_id, positions in ranks.items():
        score = sum(1.0 / (k + rank) for rank in positions.values())
        fused.append(
            RetrievalCandidate(
                chunk_id=chunk_id,
                document_id=document_ids.get(chunk_id, 0),
                doc_type=doc_types.get(chunk_id, DocType.MSDS),
                keyword_rank=positions.get("keyword"),
                vector_rank=positions.get("vector"),
                fused_score=score,
                keyword_score=scores[chunk_id].get("keyword"),
                vector_score=scores[chunk_id].get("vector"),
            )
        )
    # Ties broken by chunk_id so the order is reproducible across runs - a query
    # that returns different evidence on a retry is impossible to debug.
    fused.sort(key=lambda c: (-c.fused_score, c.chunk_id))
    return fused


def ensure_doc_type_spread(
    candidates: list[RetrievalCandidate], limit: int
) -> list[RetrievalCandidate]:
    """BR-69 - lift one candidate per missing document type into the cut.

    Law is 69% of the corpus by chunk count (measured), so a question phrased in
    legal language can fill every slot with statute text and never surface the
    MSDS entry that actually answers it.

    Only types that *have* a candidate are lifted. A type with nothing to offer
    stays absent: the alternative is fabricating relevance, and this system's
    whole contract is that shown evidence was actually retrieved (NFR-8).
    """
    if limit <= 0 or not candidates:
        return []

    head = candidates[:limit]
    present = {c.doc_type for c in head}
    missing = [c for c in candidates[limit:] if c.doc_type not in present]
    if not missing:
        return head

    result = list(head)
    for candidate in missing:
        if candidate.doc_type in {c.doc_type for c in result}:
            continue
        # Displace the weakest entry of the most over-represented type, not
        # simply the last one: dropping the tail could evict the only member of
        # another type and undo the spread we are trying to create.
        counts: dict[DocType, int] = defaultdict(int)
        for existing in result:
            counts[existing.doc_type] += 1
        dominant = max(counts, key=lambda t: (counts[t], 0))
        if counts[dominant] <= 1:
            break
        for index in range(len(result) - 1, -1, -1):
            if result[index].doc_type is dominant:
                result[index] = candidate
                break
    result.sort(key=lambda c: (-c.fused_score, c.chunk_id))
    return result


def ensure_subject_presence(
    head: list[RetrievalCandidate],
    pool: list[RetrievalCandidate],
    subject_chunk_ids: set[int],
) -> list[RetrievalCandidate]:
    """BR-65a - the substance the user named must appear in the evidence.

    BR-69's failure, one axis over. A question like "암모니아가 눈에 들어가면"
    lights up the eye section of *every* substance in both routes - the route
    words are generic, the name is not, and RRF's two-route accumulation lets
    four wrong substances' eye chunks outrank the named substance's own
    (measured, run 239: sub-06's top 4 were all other substances). An exact
    identifier hit rides one route only and structurally loses that race.

    So the guarantee mirrors `ensure_doc_type_spread`: if no chunk of the named
    subject made the head, lift the best one from the pool. Only subjects that
    *have* a candidate are lifted - `subject_chunk_ids` comes from actual
    exact-match hits (the `EXACT_MATCH_SCORE` marker BR-38 created for exactly
    this kind of downstream decision), so nothing is fabricated (NFR-8).
    Typed CAS and resolved names both qualify: each is the user naming a
    specific substance.
    """
    if not head or not subject_chunk_ids:
        return head
    if any(c.chunk_id in subject_chunk_ids for c in head):
        return head
    subject = next((c for c in pool if c.chunk_id in subject_chunk_ids), None)
    if subject is None:
        return head

    result = list(head)
    # Displace the weakest entry of the most over-represented type - the same
    # reasoning as the spread: dropping the plain tail could evict the only
    # member of another type. With every type a singleton, the overall weakest
    # goes; the subject usually shares its type anyway.
    counts: dict[DocType, int] = defaultdict(int)
    for existing in result:
        counts[existing.doc_type] += 1
    dominant = max(counts, key=lambda t: (counts[t], 0))
    if counts[dominant] > 1:
        for index in range(len(result) - 1, -1, -1):
            if result[index].doc_type is dominant:
                result[index] = subject
                break
    else:
        result[-1] = subject
    result.sort(key=lambda c: (-c.fused_score, c.chunk_id))
    return result
