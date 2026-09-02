"""C38 AnswerGenerator - BR-79~83, SP-8.

The generator's job is not only to call the model. It is to treat the model's
reply as untrusted input, because the reply was produced from evidence we did
not write (SP, threat model 1.1). Two checks do that work:

  * **ID whitelist (BR-81, SP-8)** - a cited `chunk_id` that was not in this
    request's evidence is dropped. Citing a chunk that does not exist is the
    worst failure this system has: the answer looks sourced and is not.
  * **Empty-citation retry (BR-80)** - one retry, then the sentence is removed.
    A sentence with no evidence never reaches the screen.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.adapters.llm_anthropic import ProviderRefusal
from app.core.logging import get_logger
from app.rag.assembler import PromptAssembler
from app.rag.schema_guard import validate
from app.rag.streaming import SentenceStreamParser
from app.rag.types import AnswerSentence, Evidence, GeneratedAnswer

log = get_logger(__name__)


@dataclass
class GenerationOutcome:
    sentences: list[AnswerSentence]
    refused: bool = False
    dropped_uncited: int = 0
    dropped_invalid_ids: int = 0
    prompt_name: str | None = None
    prompt_version: str | None = None


class AnswerGenerator:
    def __init__(self, llm, assembler: PromptAssembler | None = None) -> None:
        self._llm = llm
        self._assembler = assembler or PromptAssembler()

    def generate(
        self,
        question: str,
        evidence: list[Evidence],
        on_sentence_delta: Callable[[int, str], None] | None = None,
    ) -> GenerationOutcome:
        """`on_sentence_delta` receives display text as it streams (FQ2-13).

        Streaming changes nothing about correctness. What is streamed has not
        passed the id whitelist yet and has not been verified, so the caller
        must show it **without citations** until the final result arrives
        (FE-16). The alternative - badges that appear and then vanish - lets a
        user read and trust a citation that was about to be withdrawn.
        """
        allowed = {item.chunk_id for item in evidence}
        prompt = self._assembler.for_answer(question, evidence)

        try:
            payload, _ = self._call(prompt, on_sentence_delta)
        except ProviderRefusal:
            # BR-77 - a decision, not a fault. Retrying would just repeat it.
            return GenerationOutcome(
                sentences=[],
                refused=True,
                prompt_name=prompt.prompt_name,
                prompt_version=prompt.prompt_version,
            )

        answer = GeneratedAnswer.from_payload(payload)
        kept, invalid = self._apply_whitelist(answer.sentences, allowed)

        if not kept and answer.sentences:
            # BR-80 / FQ2-12 - every sentence lost its evidence. One retry, then
            # we stop: a second failure is a signal, not a coincidence.
            log.warning("regenerating_uncited_answer", extra={"sentences": len(answer.sentences)})
            try:
                # The retry is not streamed: the user has already seen the first
                # attempt's text, and streaming a replacement over it would make
                # the answer visibly rewrite itself.
                payload, _ = self._call(prompt, None)
            except ProviderRefusal:
                return GenerationOutcome(
                    sentences=[],
                    refused=True,
                    prompt_name=prompt.prompt_name,
                    prompt_version=prompt.prompt_version,
                )
            retry = GeneratedAnswer.from_payload(payload)
            kept, invalid = self._apply_whitelist(retry.sentences, allowed)
            answer = retry

        return GenerationOutcome(
            sentences=kept,
            dropped_uncited=len(answer.sentences) - len(kept),
            dropped_invalid_ids=invalid,
            prompt_name=prompt.prompt_name,
            prompt_version=prompt.prompt_version,
        )

    def _call(self, prompt, on_sentence_delta):
        """Stream when the adapter can and a listener wants it; else plain call.

        The payload is validated against the schema **on our side** regardless of
        provider (BR-79). Anthropic and Gemini both enforce it server-side, so in
        practice this never fires - but then the guarantee would belong to
        whichever provider is configured, and BR-79 is not a provider feature.
        It is what makes citation checking deterministic and it is the outermost
        injection defence.
        """
        schema = GeneratedAnswer.json_schema()
        streamer = getattr(self._llm, "stream_structured", None)

        if on_sentence_delta is None or streamer is None:
            payload, result = self._llm.generate_structured(
                prompt.user, schema, prompt.system
            )
        else:
            parser = SentenceStreamParser(on_delta=on_sentence_delta)
            payload, result = streamer(prompt.user, schema, prompt.system, parser.feed)

        verdict = validate(payload, schema)
        if not verdict:
            # Not raised: an off-schema payload is handled the same way an
            # uncited answer is - one retry, then the sentences are dropped
            # (BR-80). Raising here would turn a bad reply into a 500.
            log.warning(
                "structured_output_off_schema",
                extra={"errors": verdict.errors[:5], "provider_enforced": streamer is not None},
            )
            return {}, result
        return payload, result

    @staticmethod
    def _apply_whitelist(
        sentences: list[AnswerSentence], allowed: set[int]
    ) -> tuple[list[AnswerSentence], int]:
        """SP-8 / BR-81 - ids must come from what we actually sent."""
        kept: list[AnswerSentence] = []
        invalid = 0
        for sentence in sentences:
            valid = [cid for cid in sentence.chunk_ids if cid in allowed]
            invalid += len(sentence.chunk_ids) - len(valid)
            if not valid:
                # BR-80 - no evidence, no sentence. No exception.
                continue
            # Preserve the model's citation order but drop duplicates, which
            # would otherwise show the same source twice as if it were two.
            seen: set[int] = set()
            ordered = [cid for cid in valid if not (cid in seen or seen.add(cid))]
            kept.append(AnswerSentence(text=sentence.text, chunk_ids=ordered))
        if invalid:
            log.warning("dropped_unknown_chunk_ids", extra={"count": invalid})
        return kept, invalid
