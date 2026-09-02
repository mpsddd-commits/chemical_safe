"""C30 entity extraction — BR-64, BR-65, BR-66, and the NFR-2 budget.

The LLM path is gated on a *precondition*, not on an opinion about the model:
its only output the rules cannot already produce is `substance_names`, and
resolving those needs `substance_synonym` (BR-65), which u1 leaves empty because
the table is pre-provisioned for u3 (DD-21, UD-6).

Measured 2026-08-26: rule-only extraction produced the correct `doc_type_hint`
in 3 of 3 queries and the *same* final evidence set as the LLM path, at
0.7~46ms against 116~582ms — inside a 2,500ms retrieval budget that the rest of
retrieval already spends 165ms of.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.types import DocType
from app.rag.entities import EntityExtractor


class FakeSession:
    """No substance rows — the state u1 actually leaves behind."""

    def __init__(self, rows: list | None = None) -> None:
        self._rows = rows or []

    def execute(self, _stmt):
        rows = self._rows

        class Result:
            @staticmethod
            def all():
                return rows

        return Result()


class ExplodingLLM:
    """Calling this is the failure the test is looking for."""

    def generate_structured(self, *_args, **_kwargs):
        raise AssertionError("the LLM must not be called")


def _settings(**kw) -> Settings:
    return Settings(postgres_password="x", **kw)


class TestRulesFirst:
    def test_cas_number_short_circuits_the_llm(self):
        """BR-64 — a CAS number is a regular language; a model call is worse."""
        extractor = EntityExtractor(
            FakeSession(), ExplodingLLM(), settings=_settings(entity_llm_enabled=True)
        )
        intent = extractor.extract("7664-93-9 취급 시 보호구는?")
        assert intent.cas_numbers == ["7664-93-9"]
        assert intent.resolved_by_rules

    def test_un_number_short_circuits_the_llm(self):
        extractor = EntityExtractor(
            FakeSession(), ExplodingLLM(), settings=_settings(entity_llm_enabled=True)
        )
        assert extractor.extract("UN1830 운송 기준").un_numbers == ["1830"]


class TestGating:
    def test_llm_is_not_called_when_disabled(self):
        """The default. `ExplodingLLM` asserts if the gate leaks."""
        extractor = EntityExtractor(
            FakeSession(), ExplodingLLM(), settings=_settings(entity_llm_enabled=False)
        )
        intent = extractor.extract("황산 취급 시 보호구는?")
        assert intent.raw_terms  # rules still ran

    def test_disabled_is_the_default(self):
        assert _settings().entity_llm_enabled is False

    def test_absent_llm_is_not_an_error(self):
        intent = EntityExtractor(FakeSession(), None, settings=_settings()).extract("황산")
        assert intent.raw_terms == ["황산"]


class TestRuleHints:
    """BR-66 — a weight, never a filter. Measured correct on all three."""

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("황산 취급 시 보호구는?", DocType.MSDS),
            ("화학물질 취급자의 교육 의무는?", DocType.LAW),
            ("염산 누출 사고 사례", DocType.INCIDENT),
        ],
    )
    def test_hint_is_derived_without_a_model(self, query, expected):
        extractor = EntityExtractor(FakeSession(), None, settings=_settings())
        assert extractor.extract(query).doc_type_hint is expected

    def test_no_signal_means_no_hint(self):
        """NFR-8 — a guess would cost ranking; absence is the honest answer."""
        extractor = EntityExtractor(FakeSession(), None, settings=_settings())
        assert extractor.extract("그것은 무엇인가").doc_type_hint is None


class TestSynonyms:
    def test_empty_master_resolves_nothing(self):
        """The u1 state. `substance_synonym` is pre-provisioned for u3."""
        extractor = EntityExtractor(FakeSession([]), None, settings=_settings())
        assert extractor.extract("황산 보호구").substance_names == []

    def test_known_synonym_resolves_to_the_canonical_name(self):
        """BR-65 — and this is what makes the LLM path worth enabling later."""
        extractor = EntityExtractor(
            FakeSession([("황산", "SULFURIC ACID")]), None, settings=_settings()
        )
        intent = extractor.extract("황산 보호구")
        assert intent.substance_names == ["SULFURIC ACID"]
        # Resolved by rules, so the LLM would not be called even if enabled.
        assert intent.resolved_by_rules

    def test_unresolved_term_is_still_searched_verbatim(self):
        """Dropping it would lose the only thing the user actually named."""
        extractor = EntityExtractor(FakeSession([]), None, settings=_settings())
        assert "황산" in extractor.extract("황산 보호구").raw_terms


class TestQueryAliases:
    """BR-65a - the query-side alias map (`config/query_aliases.yaml`).

    BR-99 keeps `substance_synonym` to names the source publishes, which is
    right for cards and blind for queries: u4 measured sub-05 ("메탄올...")
    resolving to nothing because the master only knows 메틸알코올. The alias
    map closes that gap at query time only - nothing is stored, nothing is
    displayed.
    """

    def test_an_alias_resolves_to_the_canonical_term(self):
        extractor = EntityExtractor(FakeSession([]), None, settings=_settings())
        intent = extractor.extract("메탄올을 흡입하면 시각에 어떤 영향이 있나요")
        assert "메틸알코올" in intent.substance_names
        assert intent.resolved_by_rules

    def test_alias_and_synonym_do_not_duplicate(self):
        """A query naming both forms must not resolve the substance twice."""
        extractor = EntityExtractor(
            FakeSession([("메틸알코올", "메틸알코올")]), None, settings=_settings()
        )
        intent = extractor.extract("메틸알코올(메탄올) 취급 주의사항")
        assert intent.substance_names.count("메틸알코올") == 1

    def test_the_map_is_query_side_only(self):
        """The alias never lands in the DB - the session sees only SELECTs.

        FakeSession records nothing and the extractor has no write path; what
        this pins is that resolution works with an empty master, i.e. without
        anyone having stored the alias anywhere.
        """
        extractor = EntityExtractor(FakeSession([]), None, settings=_settings())
        assert extractor.extract("메탄올 독성").substance_names == ["메틸알코올"]
