"""Provider-independent schema enforcement — BR-79, NFR-21.

BR-79 is not a provider feature. Anthropic enforces it with `output_config`,
Gemini with `responseSchema`, and both would leave the guarantee owned by
whichever one is configured. The schema is what makes citation checking
deterministic (DD-8) and it is the outermost injection defence, so it is checked
on our side too.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.errors import ConfigurationError
from app.rag.schema_guard import to_gemini_schema, validate
from app.rag.types import GeneratedAnswer

ANSWER_SCHEMA = GeneratedAnswer.json_schema()
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["supported", "unsupported"]}},
    "required": ["verdict"],
    "additionalProperties": False,
}


class TestValidate:
    def test_well_formed_answer_passes(self):
        payload = {"sentences": [{"text": "본문.", "chunk_ids": [1, 2]}]}
        assert validate(payload, ANSWER_SCHEMA)

    def test_missing_required_property_fails(self):
        assert not validate({"sentences": [{"text": "본문."}]}, ANSWER_SCHEMA)

    def test_extra_property_fails(self):
        """An extra key is the visible edge of a model that ignored the contract."""
        payload = {"sentences": [{"text": "t", "chunk_ids": [1], "confidence": 0.9}]}
        result = validate(payload, ANSWER_SCHEMA)
        assert not result
        assert any("confidence" in e for e in result.errors)

    def test_wrong_element_type_fails(self):
        payload = {"sentences": [{"text": "t", "chunk_ids": ["1"]}]}
        assert not validate(payload, ANSWER_SCHEMA)

    def test_booleans_are_not_integers(self):
        """`isinstance(True, int)` is True in Python; the schema must not agree."""
        payload = {"sentences": [{"text": "t", "chunk_ids": [True]}]}
        assert not validate(payload, ANSWER_SCHEMA)

    def test_enum_is_enforced(self):
        assert validate({"verdict": "supported"}, VERDICT_SCHEMA)
        assert not validate({"verdict": "아마도"}, VERDICT_SCHEMA)

    def test_empty_payload_fails(self):
        assert not validate({}, ANSWER_SCHEMA)

    def test_errors_name_the_path(self):
        payload = {"sentences": [{"text": "t", "chunk_ids": [1]}, {"text": "t2"}]}
        result = validate(payload, ANSWER_SCHEMA)
        assert any("[1]" in e for e in result.errors)

    def test_nullable_union_type(self):
        schema = {"type": "object", "properties": {"hint": {"type": ["string", "null"]}}}
        assert validate({"hint": None}, schema)
        assert validate({"hint": "law"}, schema)
        assert not validate({"hint": 3}, schema)


class TestGeminiTranslation:
    def test_additional_properties_is_dropped(self):
        """Gemini rejects it — which is exactly why `validate` is not optional."""
        translated = to_gemini_schema(ANSWER_SCHEMA)
        assert "additionalProperties" not in translated
        assert "additionalProperties" not in translated["properties"]["sentences"]["items"]

    def test_shape_is_otherwise_preserved(self):
        translated = to_gemini_schema(ANSWER_SCHEMA)
        item = translated["properties"]["sentences"]["items"]
        assert item["type"] == "object"
        assert item["required"] == ["text", "chunk_ids"]
        assert item["properties"]["chunk_ids"]["items"]["type"] == "integer"

    def test_property_ordering_is_emitted(self):
        """Gemini honours it, and a stable field order keeps cache prefixes stable."""
        translated = to_gemini_schema(ANSWER_SCHEMA)
        item = translated["properties"]["sentences"]["items"]
        assert item["propertyOrdering"] == ["text", "chunk_ids"]

    def test_union_type_becomes_nullable(self):
        schema = {"type": "object", "properties": {"hint": {"type": ["string", "null"]}}}
        hint = to_gemini_schema(schema)["properties"]["hint"]
        assert hint["type"] == "string"
        assert hint["nullable"] is True

    def test_null_is_removed_from_enum(self):
        schema = {"type": "string", "enum": ["law", "msds", None]}
        translated = to_gemini_schema(schema)
        assert translated["enum"] == ["law", "msds"]
        assert translated["nullable"] is True

    def test_translation_output_still_validates_the_same_payloads(self):
        """The translation must not change what counts as valid."""
        payload = {"sentences": [{"text": "본문.", "chunk_ids": [1]}]}
        assert validate(payload, ANSWER_SCHEMA)
        # `additionalProperties` is the only rule dropped, so this is looser —
        # never stricter. A payload valid under the canonical schema stays valid.
        assert validate(payload, to_gemini_schema(ANSWER_SCHEMA))


class TestProviderSelection:
    """NFR-21 — the port existed in u1 so switching is an adapter, not a rewrite."""

    def _settings(self, **kw) -> Settings:
        return Settings(postgres_password="x", **kw)

    def test_default_provider_is_gemini(self):
        assert self._settings().llm_provider == "gemini"

    def test_model_defaults_follow_the_provider(self):
        assert self._settings().resolved_llm_model == "gemini-3.1-flash-lite"
        assert (
            self._settings(llm_provider="anthropic").resolved_llm_model
            == "claude-opus-5"
        )

    def test_explicit_model_wins(self):
        assert self._settings(llm_model="gemini-3.5-flash").resolved_llm_model == (
            "gemini-3.5-flash"
        )

    def test_unknown_provider_is_rejected_at_config_time(self):
        """A typo must not quietly run a model whose Korean quality is unassessed."""
        with pytest.raises(ValueError, match="LLM_PROVIDER"):
            self._settings(llm_provider="gpt")

    def test_factory_rejects_unknown_provider(self):
        from app.adapters.llm_factory import build_llm

        settings = self._settings()
        object.__setattr__(settings, "llm_provider", "mystery")
        with pytest.raises(ConfigurationError):
            build_llm(settings)

    def test_factory_builds_without_a_key(self):
        """BR-02 — construction must not require the key; only calling does."""
        from app.adapters.llm_factory import build_llm

        adapter = build_llm(self._settings())
        assert adapter.model == "gemini-3.1-flash-lite"


class TestFreeTierPricing:
    def test_free_model_is_zero_not_unknown(self):
        """A genuine 0 and a missing price are different facts (BR-96, NFR-20)."""
        from app.rag.pricing import PricingTable

        table = PricingTable()
        cost = table.cost_for(
            "gemini-3.1-flash-lite", input_tokens=1_000_000, output_tokens=1_000_000
        )
        assert cost == 0
        assert table.has("gemini-3.1-flash-lite")

    def test_unregistered_model_is_none(self):
        from app.rag.pricing import PricingTable

        cost = PricingTable().cost_for(
            "some-unknown-model", input_tokens=1000, output_tokens=1000
        )
        assert cost is None
