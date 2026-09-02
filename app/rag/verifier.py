"""C40 SupportVerifier - BR-85~87, SP-6, PP-5.

This is the second, independent line of defence. It matters that it is
*independent*: the generator and the verifier read the same evidence, so if the
verifier were given the same framing it could be talked into the same mistake.
Three things keep them apart.

  * A different prompt file with a different system instruction (CP-2).
  * A deliberately narrow input - one sentence, its own evidence, and nothing
    else. Not the question, not sibling sentences (SP-6).
  * A structured `SupportVerdict` output rather than free text.

Concurrency is capped (PP-5) and the cap is about isolation rather than speed:
an unbounded fan-out lets one long answer exhaust the rate limit and fail other
users' queries.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.errors import QuotaExhaustedError
from app.core.logging import get_logger
from app.core.types import SupportVerdict
from app.rag.assembler import PromptAssembler
from app.rag.schema_guard import validate
from app.rag.types import AnswerSentence, Evidence

log = get_logger(__name__)

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["supported", "unsupported"]},
    },
    "required": ["verdict"],
    "additionalProperties": False,
}


@dataclass
class VerifiedSentence:
    sentence: AnswerSentence
    verdict: SupportVerdict
    # Why it was unverified. BR-87 removes the sentence either way, but "we
    # judged it and it failed" and "we never got to ask" are different facts and
    # the screen must not present them as one.
    unverified_by_quota: bool = False

    @property
    def kept(self) -> bool:
        return self.verdict is SupportVerdict.SUPPORTED


class SupportVerifier:
    def __init__(
        self,
        llm,
        assembler: PromptAssembler | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._llm = llm
        self._assembler = assembler or PromptAssembler()
        self._settings = settings or get_settings()

    def verify_all(
        self, sentences: list[AnswerSentence], evidence_by_id: dict[int, Evidence]
    ) -> list[VerifiedSentence]:
        if not sentences:
            return []
        workers = min(self._settings.verify_concurrency, len(sentences))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(
                pool.map(lambda s: self.verify_one(s, evidence_by_id), sentences)
            )

    def verify_one(
        self, sentence: AnswerSentence, evidence_by_id: dict[int, Evidence]
    ) -> VerifiedSentence:
        cited = [evidence_by_id[cid] for cid in sentence.chunk_ids if cid in evidence_by_id]
        if not cited:
            # BR-85 - support means *its own* evidence supports it. With none
            # cited there is nothing to check against.
            return VerifiedSentence(sentence, SupportVerdict.UNSUPPORTED)

        prompt = self._assembler.for_verification(sentence.text, cited)
        try:
            payload, _ = self._llm.generate_structured(
                prompt.user, _VERDICT_SCHEMA, prompt.system
            )
        except QuotaExhaustedError as exc:
            # Removed all the same (BR-87), but recorded as "not asked" rather
            # than "asked and failed". On the free tier this is the ordinary way
            # a development session ends, and it must not read as the verifier
            # rejecting a correct answer.
            log.warning("verification_quota_exhausted", extra={"error": exc.message})
            return VerifiedSentence(
                sentence, SupportVerdict.UNVERIFIED, unverified_by_quota=True
            )
        except Exception as exc:  # noqa: BLE001 - BR-87 covers every failure mode
            # Not verified is not the same as verified-and-passed. Both are
            # removed; only one of them is recorded as checked (R-6).
            log.warning("verification_failed", extra={"error": str(exc)})
            return VerifiedSentence(sentence, SupportVerdict.UNVERIFIED)

        if not validate(payload, _VERDICT_SCHEMA):
            # BR-87 - an off-schema verdict is a verification that did not
            # happen, not a permissive one.
            log.warning("verdict_off_schema", extra={"payload": str(payload)[:200]})
            return VerifiedSentence(sentence, SupportVerdict.UNVERIFIED)

        raw = str((payload or {}).get("verdict", "")).strip().lower()
        if raw == SupportVerdict.SUPPORTED.value:
            return VerifiedSentence(sentence, SupportVerdict.SUPPORTED)
        if raw == SupportVerdict.UNSUPPORTED.value:
            return VerifiedSentence(sentence, SupportVerdict.UNSUPPORTED)
        # A verdict we cannot read is a verification that did not happen.
        log.warning("unreadable_verdict", extra={"payload": str(payload)[:200]})
        return VerifiedSentence(sentence, SupportVerdict.UNVERIFIED)
