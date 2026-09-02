"""C45 RetrievalMetrics - FR-37, BR-113, BR-124.

**No LLM call reaches this file.** That is the reason `--retrieval-only` can run
the whole set every day for nothing, and it is not an optimisation: the two
worst retrieval defects this project has had - u2 defect 27 (the refusal gate
thresholding an RRF rank score, which cannot separate a good query from a bad
one) and defect 45 (an exact CAS match overruled by cosine similarity) - both
happened before generation, and both would show up here as a Recall or MRR drop.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.evaluation.types import EvidenceRef, RetrievalScore, RetrievedRef

DEFAULT_KS: tuple[int, ...] = (5, 10)


def matches(ref: EvidenceRef, candidate: RetrievedRef, document_id: int) -> bool:
    """Does this candidate satisfy this piece of expected evidence?

    Document-level when the golden set names no section (BR-113). That is not
    laxity: those documents genuinely have no section on their chunks, because
    BR-31a folded them into one - 13 documents in the corpus, every incident
    record among them. Scoring them by section would score them as always wrong.
    """
    if candidate.document_id != document_id:
        return False
    if ref.section is None:
        return True
    return candidate.section_code == ref.section


def score(
    evidence: Sequence[EvidenceRef],
    retrieved: Sequence[RetrievedRef],
    resolve: dict[tuple[str, str], int],
    ks: Iterable[int] = DEFAULT_KS,
) -> RetrievalScore:
    """Recall@k for each k, plus the reciprocal rank of the first hit.

    `resolve` maps (source, external_id) to a document id. It is passed in
    rather than looked up here so this stays a pure function - the service does
    the one query that resolves every reference in the set at once.
    """
    ks = tuple(ks)
    expected = [ref for ref in evidence if (ref.source, ref.external_id) in resolve]
    if not expected:
        # Either the question expects a refusal, or its evidence does not
        # resolve - and the loader refuses to start in the second case, so this
        # is the refusal path. Recall of nothing is 1.0, not 0.0: reporting 0
        # would drag the average down for questions that were never meant to
        # retrieve anything.
        return RetrievalScore(
            recall={k: 1.0 for k in ks}, reciprocal_rank=1.0, hits=0, expected=0
        )

    ordered = sorted(retrieved, key=lambda item: item.rank)
    recall: dict[int, float] = {}
    for k in ks:
        window = ordered[:k]
        hit = sum(
            1
            for ref in expected
            if any(matches(ref, c, resolve[(ref.source, ref.external_id)]) for c in window)
        )
        recall[k] = round(hit / len(expected), 3)

    reciprocal = 0.0
    for candidate in ordered:
        if any(
            matches(ref, candidate, resolve[(ref.source, ref.external_id)])
            for ref in expected
        ):
            reciprocal = round(1.0 / (candidate.rank + 1), 3)
            break

    widest = max(ks)
    hits = sum(
        1
        for ref in expected
        if any(
            matches(ref, c, resolve[(ref.source, ref.external_id)]) for c in ordered[:widest]
        )
    )
    return RetrievalScore(
        recall=recall, reciprocal_rank=reciprocal, hits=hits, expected=len(expected)
    )
