"""Provider selection (NFR-21).

One place decides which adapter is built, so nothing in `rag/` or `services/`
ever names a provider. That was the point of putting `LLMPort` in u1 before
anything implemented it (DD-6, DD-21), and switching the default from Anthropic
to Gemini touched no rule, no workflow and no test in `rag/`.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError


def build_llm(settings: Settings | None = None):
    settings = settings or get_settings()
    provider = (settings.llm_provider or "").strip().lower()

    if provider == "gemini":
        from app.adapters.llm_gemini import GeminiLLMAdapter

        return GeminiLLMAdapter(settings)
    if provider == "anthropic":
        from app.adapters.llm_anthropic import AnthropicLLMAdapter

        return AnthropicLLMAdapter(settings)

    # Fail loudly at construction rather than defaulting: a typo here would
    # silently bill the wrong provider, or quietly use a model whose Korean
    # safety-text quality was never assessed (R-6).
    raise ConfigurationError(
        f"unknown LLM_PROVIDER: {settings.llm_provider!r} (expected 'gemini' or 'anthropic')"
    )


def build_entity_llm(settings: Settings | None = None):
    """A deliberately impatient client for C30 entity extraction (BR-64).

    Entity extraction improves ranking; the query answers without it. It also
    sits inside the NFR-2 retrieval budget, so retrying it is backwards: a step
    whose failure costs a little relevance must not be allowed to cost the whole
    latency budget.

    Measured 2026-08-25: sharing the main retry policy let a 503 model turn a
    339ms retrieval into 69 seconds of retries. No retries, short timeout.
    """
    settings = settings or get_settings()
    return build_llm(
        settings.model_copy(
            update={
                "llm_max_retries": 0,
                "llm_rate_limit_retries": 0,
                "llm_timeout_seconds": settings.entity_llm_timeout_seconds,
            }
        )
    )


def build_verify_llm(settings: Settings | None = None):
    """The client for stage-two grounding verification (BR-85~87).

    A different model from generation, for two reasons that point the same way.

    The free tier meters requests **per model** (20/day, measured 2026-08-26),
    and verification is the multiplier - one call per sentence (BR-86a). Sharing
    a model means generation and verification drain one pool together.

    And the task genuinely is smaller: SP-6 gives the verifier one sentence, its
    own evidence, an enum to answer with, and deliberately not the question.
    A lite model is a fit for that, not a concession.
    """
    settings = settings or get_settings()
    return build_llm(
        settings.model_copy(
            update={
                "llm_model": settings.verify_model,
                "llm_timeout_seconds": settings.verify_llm_timeout_seconds,
            }
        )
    )


def build_judge_llm(settings: Settings | None = None):
    """The client for u4's evaluation judge (FR-38, BR-122).

    A **third** model, and the reason is arithmetic rather than taste. Free-tier
    quota is metered per model (20/day), an answered query already costs 5.25
    calls across generation and verification, and a full run needs one judge
    call per question on top. Putting the judge on the answer model would spend
    the answers to buy the grading.

    Judging is also not latency-bound - nothing waits on it, and a run takes days
    regardless - so it gets the generous timeout that generation cannot afford.
    """
    settings = settings or get_settings()
    if not settings.judge_model:
        raise ConfigurationError(
            "JUDGE_MODEL 이 설정되지 않았습니다 - 평가 심판은 답변 모델과 다른 "
            "모델이어야 합니다 (BR-122)"
        )
    if settings.judge_model == settings.resolved_llm_model:
        # BR-122. Refused rather than warned: sharing the pool means a full run
        # cannot finish, and a model grading its own output grades it kindly.
        raise ConfigurationError(
            f"JUDGE_MODEL 이 답변 모델과 같습니다 ({settings.judge_model}). "
            "무료 티어 할당량은 모델당이라 같은 모델을 쓰면 평가가 답변 할당량을 "
            "잠식합니다 (BR-122)"
        )
    return build_llm(
        settings.model_copy(
            update={
                "llm_model": settings.judge_model,
                "llm_timeout_seconds": settings.judge_llm_timeout_seconds,
            }
        )
    )
