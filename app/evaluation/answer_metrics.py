"""C46 AnswerMetrics - FR-37, NFR-5, BR-125·BR-127·BR-128.

Also no LLM call. Accuracy is the judge's job (C47); everything measurable
against the golden set without asking a model is measured here.

**Citation precision is an approximation and it is written down as one.** NFR-5
says the source attached to a sentence must actually contain what the sentence
claims, and checking that literally means one judge call per sentence - five to
nine more per question, which puts a full run past two weeks of free-tier quota.
So a citation counts as correct when it points inside the evidence a person
marked as the answer's home.

The approximation errs **upward**: a sentence can cite the right section and
still say something the section does not support. Faithfulness (C47) looks at
the same thing from the other side, and the two disagreeing on a question is the
signal that a human should read it.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.evaluation.types import EvidenceRef, RetrievedRef

REFUSAL_PREFIX = "refused"


def citation_precision(
    evidence: Sequence[EvidenceRef],
    citations: Sequence[RetrievedRef],
    resolve: dict[tuple[str, str], int],
) -> float | None:
    """Share of cited chunks that sit inside the expected evidence.

    None when the answer cited nothing - that is not precision 0.0. An answer
    with no citations is a different failure (BR-81 dropped every id, or the
    answer was refused), and averaging it in as a zero would hide which one
    happened.
    """
    if not citations:
        return None
    targets = [
        (ref, resolve[(ref.source, ref.external_id)])
        for ref in evidence
        if (ref.source, ref.external_id) in resolve
    ]
    if not targets:
        return None

    from app.evaluation.retrieval_metrics import matches

    correct = sum(
        1
        for cited in citations
        if any(matches(ref, cited, document_id) for ref, document_id in targets)
    )
    return round(correct / len(citations), 3)


def is_refusal(outcome: str | None) -> bool:
    """BR-127 - the outcome family, not the reason.

    Scoring the reason would break the golden set every time the refusal
    taxonomy is refined, and FR-37 asks a simpler question: did it refuse the
    question that should have been refused?
    """
    return bool(outcome) and str(outcome).startswith(REFUSAL_PREFIX)


def refusal_correct(expects_refusal: bool, outcome: str | None) -> bool:
    return is_refusal(outcome) if expects_refusal else not is_refusal(outcome)


def refusal_rates(items: Sequence[tuple[bool, str | None]]) -> dict[str, float | None]:
    """Refusal accuracy and false-refusal rate, always together (BR-128).

    Reporting accuracy alone would give a system that refuses everything a
    perfect score. `items` is (expects_refusal, outcome).
    """
    wanted = [outcome for expects, outcome in items if expects]
    unwanted = [outcome for expects, outcome in items if not expects]
    return {
        "accuracy": (
            round(sum(1 for o in wanted if is_refusal(o)) / len(wanted), 3) if wanted else None
        ),
        "false_refusal": (
            round(sum(1 for o in unwanted if is_refusal(o)) / len(unwanted), 3)
            if unwanted
            else None
        ),
    }
