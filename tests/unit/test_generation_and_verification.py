"""Generation and grounding verification — BR-79~87, SP-6, SP-8, PP-5.

The model's reply is untrusted input here. It was produced from evidence we did
not write, so everything it claims about ids and support gets checked.
"""

from __future__ import annotations

import threading

import pytest

from app.adapters.llm_anthropic import ProviderRefusal
from app.core.types import DocType, SupportVerdict
from app.ports.llm import LLMResult
from app.rag.generator import AnswerGenerator
from app.rag.types import AnswerSentence, Evidence
from app.rag.verifier import SupportVerifier


def _evidence(chunk_id: int, text: str = "본문") -> Evidence:
    return Evidence(
        chunk_id=chunk_id,
        document_id=1,
        source_url="https://example.test/d",
        document_title="문서",
        section_code="msds_08",
        section_title="보호구",
        text=text,
        start_offset=0,
        end_offset=len(text),
        score=0.5,
        doc_type=DocType.MSDS,
    )


class FakeLLM:
    """Returns queued payloads; records how many calls were made."""

    def __init__(self, *payloads):
        self._payloads = list(payloads)
        self.calls = 0

    def generate_structured(self, prompt, schema, system=None):
        self.calls += 1
        payload = self._payloads.pop(0) if self._payloads else {"sentences": []}
        if isinstance(payload, Exception):
            raise payload
        return payload, LLMResult(
            model="test", input_tokens=1, output_tokens=1, latency_ms=1.0, ok=True
        )


class TestIdWhitelist:
    def test_unknown_chunk_id_is_dropped(self):
        """BR-81 / SP-8 — citing a chunk we never sent is the worst failure."""
        llm = FakeLLM({"sentences": [{"text": "문장.", "chunk_ids": [1, 999]}]})
        out = AnswerGenerator(llm).generate("q", [_evidence(1)])
        assert out.sentences[0].chunk_ids == [1]
        assert out.dropped_invalid_ids == 1

    def test_sentence_with_only_invalid_ids_is_removed(self):
        llm = FakeLLM(
            {"sentences": [{"text": "허구.", "chunk_ids": [777]}]},
            {"sentences": [{"text": "허구.", "chunk_ids": [777]}]},
        )
        out = AnswerGenerator(llm).generate("q", [_evidence(1)])
        assert out.sentences == []

    def test_duplicate_citations_are_collapsed(self):
        """One source shown twice reads as two independent sources."""
        llm = FakeLLM({"sentences": [{"text": "문장.", "chunk_ids": [1, 1, 2]}]})
        out = AnswerGenerator(llm).generate("q", [_evidence(1), _evidence(2)])
        assert out.sentences[0].chunk_ids == [1, 2]


class TestUncitedSentences:
    def test_uncited_sentence_triggers_one_retry(self):
        """BR-80 / FQ2-12 — one retry, then stop. Twice is a signal."""
        llm = FakeLLM(
            {"sentences": [{"text": "근거 없음.", "chunk_ids": []}]},
            {"sentences": [{"text": "근거 있음.", "chunk_ids": [1]}]},
        )
        out = AnswerGenerator(llm).generate("q", [_evidence(1)])
        assert llm.calls == 2
        assert [s.text for s in out.sentences] == ["근거 있음."]

    def test_no_retry_when_some_sentences_are_cited(self):
        llm = FakeLLM(
            {
                "sentences": [
                    {"text": "근거 있음.", "chunk_ids": [1]},
                    {"text": "근거 없음.", "chunk_ids": []},
                ]
            }
        )
        out = AnswerGenerator(llm).generate("q", [_evidence(1)])
        assert llm.calls == 1
        assert len(out.sentences) == 1
        assert out.dropped_uncited == 1


class TestProviderRefusal:
    def test_refusal_is_terminal_not_retried(self):
        """BR-77 — retrying a decision just repeats it."""
        llm = FakeLLM(ProviderRefusal("test", None))
        out = AnswerGenerator(llm).generate("q", [_evidence(1)])
        assert out.refused is True
        assert llm.calls == 1


class TestVerifier:
    def test_supported_is_kept(self):
        verifier = SupportVerifier(FakeLLM({"verdict": "supported"}))
        result = verifier.verify_one(
            AnswerSentence("문장.", [1]), {1: _evidence(1)}
        )
        assert result.verdict is SupportVerdict.SUPPORTED
        assert result.kept

    def test_unsupported_is_removed(self):
        verifier = SupportVerifier(FakeLLM({"verdict": "unsupported"}))
        result = verifier.verify_one(AnswerSentence("문장.", [1]), {1: _evidence(1)})
        assert not result.kept

    def test_call_failure_is_unverified_not_supported(self):
        """BR-87 / R-6 — failing to check is not the same as checking and passing.

        Both are removed; only one is *recorded* as verified, and in safety
        information that distinction has to survive into the log.
        """
        verifier = SupportVerifier(FakeLLM(RuntimeError("boom")))
        result = verifier.verify_one(AnswerSentence("문장.", [1]), {1: _evidence(1)})
        assert result.verdict is SupportVerdict.UNVERIFIED
        assert not result.kept

    def test_unreadable_verdict_is_unverified(self):
        verifier = SupportVerifier(FakeLLM({"verdict": "아마도"}))
        result = verifier.verify_one(AnswerSentence("문장.", [1]), {1: _evidence(1)})
        assert result.verdict is SupportVerdict.UNVERIFIED

    def test_sentence_without_resolvable_evidence_is_unsupported(self):
        """BR-85 — support means *its own* evidence supports it."""
        verifier = SupportVerifier(FakeLLM({"verdict": "supported"}))
        result = verifier.verify_one(AnswerSentence("문장.", [42]), {1: _evidence(1)})
        assert result.verdict is SupportVerdict.UNSUPPORTED


class CountingLLM:
    """Tracks peak concurrency across threads."""

    def __init__(self) -> None:
        self.peak = 0
        self._live = 0
        self._lock = threading.Lock()

    def generate_structured(self, prompt, schema, system=None):
        with self._lock:
            self._live += 1
            self.peak = max(self.peak, self._live)
        # hold long enough for siblings to pile up if the cap were absent
        threading.Event().wait(0.05)
        with self._lock:
            self._live -= 1
        return {"verdict": "supported"}, LLMResult(
            model="test", input_tokens=1, output_tokens=1, latency_ms=1.0, ok=True
        )


class TestConcurrencyCap:
    def test_verification_respects_the_cap(self, settings):
        """PP-5 — the cap is about isolation, not speed.

        Unbounded fan-out lets one long answer exhaust the rate limit and take
        other users' queries down with it.
        """
        llm = CountingLLM()
        verifier = SupportVerifier(
            llm, settings=settings.model_copy(update={"verify_concurrency": 2})
        )
        sentences = [AnswerSentence(f"문장 {i}.", [1]) for i in range(8)]
        verifier.verify_all(sentences, {1: _evidence(1)})
        assert llm.peak <= 2

    def test_empty_input_makes_no_calls(self, settings):
        llm = CountingLLM()
        SupportVerifier(llm, settings=settings).verify_all([], {})
        assert llm.peak == 0


@pytest.mark.parametrize("payload", [{}, {"sentences": None}, {"sentences": []}])
def test_malformed_payloads_do_not_raise(payload):
    out = AnswerGenerator(FakeLLM(payload, payload)).generate("q", [_evidence(1)])
    assert out.sentences == []


class TestQuotaIsNotAJudgment:
    """BR-87 removes the sentence either way — but the two are different facts.

    A sentence judged unsupported and a sentence we never got to ask about must
    not read the same. On the free tier (20 requests/day per model, measured
    2026-08-26) the second is the ordinary way a development session ends, and
    presenting it as "the evidence did not support this" would be a lie about
    what happened.
    """

    def test_quota_exhaustion_is_flagged(self):
        from app.core.errors import QuotaExhaustedError

        verifier = SupportVerifier(FakeLLM(QuotaExhaustedError("spent", retry_after_seconds=34)))
        result = verifier.verify_one(AnswerSentence("문장.", [1]), {1: _evidence(1)})

        assert result.verdict is SupportVerdict.UNVERIFIED
        assert result.unverified_by_quota is True
        assert not result.kept  # still removed — BR-87 does not bend

    def test_ordinary_failure_is_not_flagged_as_quota(self):
        verifier = SupportVerifier(FakeLLM(RuntimeError("boom")))
        result = verifier.verify_one(AnswerSentence("문장.", [1]), {1: _evidence(1)})

        assert result.verdict is SupportVerdict.UNVERIFIED
        assert result.unverified_by_quota is False

    def test_a_judged_rejection_is_not_flagged_either(self):
        verifier = SupportVerifier(FakeLLM({"verdict": "unsupported"}))
        result = verifier.verify_one(AnswerSentence("문장.", [1]), {1: _evidence(1)})

        assert result.verdict is SupportVerdict.UNSUPPORTED
        assert result.unverified_by_quota is False
