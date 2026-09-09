"""N1 PromptAssembler - SP-1, SP-2, SP-3, SP-7, BR-94.

Three things happen here, and each is a separate defence:

  * **Role split (SP-1).** Instructions go in `system`, evidence and the question
    go in `user`. The trust boundary is then an API-level fact rather than a
    string-parsing convention.
  * **Escaping (SP-3).** Evidence bodies are XML-escaped, so a `<` cannot appear
    in them at all.
  * **Per-request nonce (SP-3).** The block tags carry random hex. Even if some
    encoding trick survived escaping, the text would have to guess *this
    request's* tag name.

The nonce is not free of trade-offs and it is worth naming the one it has: it
makes the evidence block uncacheable. That costs nothing in practice, because
evidence differs per query anyway - BR-94's cached prefix is the fixed system
prompt, which carries no nonce.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.rag.prompts import Prompt, PromptRepository, shared_repository
from app.rag.sanitize import escape_attr, escape_for_prompt
from app.rag.types import Evidence


@dataclass(frozen=True)
class AssembledPrompt:
    system: str
    user: str
    prompt_name: str
    prompt_version: str


class PromptAssembler:
    def __init__(
        self,
        repository: PromptRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repo = repository or shared_repository()
        self._settings = settings or get_settings()

    @staticmethod
    def _nonce() -> str:
        return secrets.token_hex(4)

    def clip_question(self, question: str) -> str:
        """SP-7 - without a ceiling the question can outgrow the evidence."""
        limit = self._settings.query_max_chars
        return question[:limit]

    def for_answer(self, question: str, evidence: list[Evidence]) -> AssembledPrompt:
        prompt: Prompt = self._repo.get("answer")
        nonce = self._nonce()
        ev_tag, q_tag = f"evidence-{nonce}", f"question-{nonce}"

        blocks = []
        for item in evidence:
            attrs = (
                f'id="{item.chunk_id}" '
                f'doc_type="{escape_attr(item.doc_type.value)}" '
                f'title="{escape_attr(item.document_title or "")}" '
                f'section="{escape_attr(item.section_code or "")}" '
                f'suspected_injection="{"true" if item.suspected_injection else "false"}"'
            )
            blocks.append(
                f"<{ev_tag} {attrs}>\n{escape_for_prompt(item.text)}\n</{ev_tag}>"
            )

        user = "\n\n".join(
            [
                *blocks,
                f"<{q_tag}>\n{escape_for_prompt(self.clip_question(question))}\n</{q_tag}>",
            ]
        )
        return AssembledPrompt(
            system=prompt.text,
            user=user,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
        )

    def for_verification(self, sentence: str, evidence: list[Evidence]) -> AssembledPrompt:
        """SP-6 - the verifier gets the sentence and its own evidence. Nothing else.

        No question, no sibling sentences, no other evidence. A verifier with
        less context has less to be steered about, and "is this sentence in this
        text" leaves almost no discretion to hijack.

        `title` is not an exception to that. SP-6 keeps out the context the
        *user* controls - the question and the neighbouring sentences - because
        that is what a hijack steers with. A chunk's own document title is not
        user context, it is which document this evidence is: substance-record
        chunks carry no substance name in their body, so without the title the
        verifier reads an anonymous "·눈에 소량은 영구적은 손상을 일으킬 것임" and
        cannot tell that the sentence naming 암모니아 is talking about it. It then
        has to say unsupported, which is what query 492 did to three correct
        sentences. Same value, same escaping as `for_answer`, so no new exposure
        surface: a user-uploaded document's title already reaches the generator
        by this route.

        `section` is deliberately left out. A section code (`substance_eye`,
        `msds_08`) is not the identity of the evidence, it is a claim *about* its
        topic, and the verifier's whole job is to check claims against the body
        text only. Told the section is the eye one, it could count that as
        support for a sentence about eyes that the body never states - the
        partial-support rule the prompt is built on. The title resolves who; the
        body must stay the only source of what.
        """
        prompt: Prompt = self._repo.get("verify")
        nonce = self._nonce()
        ev_tag, s_tag = f"evidence-{nonce}", f"sentence-{nonce}"

        blocks = [
            f'<{ev_tag} id="{item.chunk_id}" '
            f'title="{escape_attr(item.document_title or "")}">\n'
            f"{escape_for_prompt(item.text)}\n</{ev_tag}>"
            for item in evidence
        ]
        user = "\n\n".join(
            [*blocks, f"<{s_tag}>\n{escape_for_prompt(sentence)}\n</{s_tag}>"]
        )
        return AssembledPrompt(
            system=prompt.text,
            user=user,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
        )

    def for_entity(self, question: str) -> AssembledPrompt:
        prompt: Prompt = self._repo.get("entity")
        nonce = self._nonce()
        q_tag = f"question-{nonce}"
        user = f"<{q_tag}>\n{escape_for_prompt(self.clip_question(question))}\n</{q_tag}>"
        return AssembledPrompt(
            system=prompt.text,
            user=user,
            prompt_name=prompt.name,
            prompt_version=prompt.version,
        )
