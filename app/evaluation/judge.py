"""C47 LLMJudge - FR-38, BR-122·BR-123·BR-126.

One call per question, returning **both** verdicts. FR-38 makes a judge call
unavoidable for faithfulness, so accuracy rides along in the same call: asking
twice doubles the only expensive part of the run and buys nothing.

The judge runs on a different model from the answer (BR-122). Two reasons, and
the mundane one is the binding one here: free-tier quota is counted per model,
so judging on a second model does not eat the twenty answers a day. The other is
that a model grading its own output grades it generously.

What the judge is **not** given: where the golden set says the answer lives.
Handing it the expected evidence location would let it mark a citation correct
by reading the answer key. It gets the question, the expected points, the actual
answer, and the evidence the answer was built from - nothing about which of that
evidence was supposed to be used.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.evaluation.types import GoldenQuestion, Judgement
from app.rag.prompts import PromptRepository, shared_repository
from app.rag.sanitize import escape_for_prompt

log = get_logger(__name__)

MAX_EVIDENCE_CHARS = 6000
MAX_ANSWER_CHARS = 4000


class LLMJudge:
    def __init__(
        self,
        llm,
        repository: PromptRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._llm = llm
        self._repo = repository or shared_repository()
        self._settings = settings or get_settings()

    @property
    def prompt_version(self) -> str:
        return self._repo.get("judge").version

    def judge(
        self, question: GoldenQuestion, answer_text: str, evidence_texts: list[str]
    ) -> Judgement:
        """Raises whatever the provider raises - quota included.

        Deliberately not caught here. The service turns a quota error into a
        resumable `partial` run (BR-118), and swallowing it into a `False`
        verdict would record "the answer was wrong" when what happened was
        "we never asked".
        """
        prompt = self._render(question, answer_text, evidence_texts)
        payload, _result = self._llm.generate_structured(prompt, Judgement.json_schema())
        return Judgement(
            correct=bool(payload.get("correct")),
            faithful=bool(payload.get("faithful")),
            reason=str(payload.get("reason") or "").strip(),
        )

    def _render(
        self, question: GoldenQuestion, answer_text: str, evidence_texts: list[str]
    ) -> str:
        template = self._repo.get("judge").text
        points = "\n".join(f"- {escape_for_prompt(p)}" for p in question.answer_points)
        joined = "\n\n---\n\n".join(evidence_texts)
        # C7 - the cap used to bite silently, so evidence the judge never saw
        # came back as a faithfulness failure and looked like a quality drop.
        # Whatever is dropped here cannot be judged, and that has to be visible
        # in the log rather than only in the metric.
        if len(joined) > MAX_EVIDENCE_CHARS:
            log.warning(
                "judge_evidence_truncated",
                extra={
                    "question_id": question.id,
                    "evidence_chars": len(joined),
                    "limit": MAX_EVIDENCE_CHARS,
                    "dropped_chars": len(joined) - MAX_EVIDENCE_CHARS,
                },
            )
        evidence = escape_for_prompt(joined[:MAX_EVIDENCE_CHARS])
        return (
            template.replace("{question}", escape_for_prompt(question.question))
            .replace("{expected_points}", points)
            .replace("{actual_answer}", escape_for_prompt(answer_text[:MAX_ANSWER_CHARS]))
            .replace("{evidence}", evidence)
        )
