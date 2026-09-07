"""C8(a) — every Gemini call is greedy, whatever it is for.

The refusal set moved between runs 387 and 549 with no change to the generator
or the verifier: the same code answered twice and stage two (BR-87) removed a
different question each time. A refused question leaves the accuracy and
faithfulness denominators, so that flip moves every rate by 1/24 while the
0.05 guards stay quiet. These tests pin the config that stops it.

The adapter is constructed but never called out (NFR-28): `_config` builds a
request object and touches neither the network nor the API key.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings


def _adapter():
    pytest.importorskip(
        "google.genai", reason="provider SDK lives in the app container (NFR-28)"
    )
    from app.adapters.llm_gemini import GeminiLLMAdapter

    return GeminiLLMAdapter(Settings(postgres_password="x", llm_provider="gemini"))


SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


class TestTemperatureIsPinned:
    def test_a_bare_call_carries_zero(self):
        """`generate()` passes no system prompt and no schema."""
        assert _adapter()._config(None, None).temperature == 0.0

    def test_a_system_instruction_does_not_displace_it(self):
        """BR-94's cache prefix and the temperature are independent kwargs."""
        config = _adapter()._config("지시문", None)

        assert config.temperature == 0.0
        assert config.system_instruction == "지시문"

    def test_a_response_schema_does_not_displace_it(self):
        """BR-79's structured output is where verify and judge live."""
        config = _adapter()._config(None, SCHEMA)

        assert config.temperature == 0.0
        assert config.response_mime_type == "application/json"
        assert config.response_schema is not None

    def test_schema_and_system_together_still_carry_it(self):
        """The answer path sends both, and it is the one that was flipping."""
        config = _adapter()._config("지시문", SCHEMA)

        assert config.temperature == 0.0
        assert config.system_instruction == "지시문"
        assert config.response_schema is not None


class TestEveryPurposeGoesThroughIt:
    """answer, verify, judge and entity are four wrappers over one adapter.

    They differ by `LlmPurpose` for cost accounting (BR-86a), not by client, so
    pinning `_config` pins all four. What this asserts is the part that could
    silently stop being true: that each port method still builds its request
    through `_config` rather than assembling one of its own.
    """

    def _captured(self, method: str):
        adapter = _adapter()
        seen: list = []

        class _Models:
            def generate_content(self, *, model, contents, config):
                seen.append(config)
                return _Response()

            def generate_content_stream(self, *, model, contents, config):
                seen.append(config)
                return iter([_Chunk()])

        class _Client:
            models = _Models()

        class _Chunk:
            text = '{"answer": "가"}'
            candidates: list = []
            usage_metadata = None

        class _Response:
            text = '{"answer": "가"}'
            candidates: list = []
            prompt_feedback = None
            usage_metadata = None

        adapter._client = _Client()
        if method == "generate":
            adapter.generate("질문", system="지시문")
        elif method == "generate_structured":
            adapter.generate_structured("질문", SCHEMA, system="지시문")
        else:
            adapter.stream_structured("질문", SCHEMA, system="지시문")
        assert len(seen) == 1
        return seen[0]

    @pytest.mark.parametrize(
        "method", ["generate", "generate_structured", "stream_structured"]
    )
    def test_the_request_config_carries_zero(self, method: str):
        assert self._captured(method).temperature == 0.0
