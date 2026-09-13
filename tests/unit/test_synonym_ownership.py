"""D11 follow-up - two producers write `substance_synonym`, each replaces only its own.

`replace_synonyms()` used to clear every row of a substance and put back what the
NCIS projection derives. After the D11 backfill added 46 rows of other types, the
next re-index of `ncis_substance` would have deleted all of them without a word.

BR-98 still holds for the projection's own rows: a change in how a name is
derived must replace the old spelling, not sit beside it (2026-08-26, 160 rows
instead of 80). Both halves are pinned here, without a database.
"""

from __future__ import annotations

import re

import pytest

from app.core.types import SynonymType
from app.db.models import Substance, SubstanceSynonym
from app.db.repositories.catalog import SubstanceRepo
from app.substances.lookup import ALIAS_SYNONYM_TYPES, KeySupport, SubstanceLookup, classify_alias
from app.substances.projection import PROJECTED_SYNONYM_TYPES, extract_facts, project


class _FlushOnly:
    def flush(self) -> None:
        pass


def _substance(*rows: tuple[str, SynonymType]) -> Substance:
    substance = Substance(cas_number="7664-93-9", name_ko="황산", name_en="Sulfuric acid")
    for term, kind in rows:
        substance.synonyms.append(
            SubstanceSynonym(term=term, normalized_term=term.lower(), term_type=kind.value)
        )
    return substance


def _rows(substance: Substance) -> set[tuple[str, str]]:
    return {(s.term, s.term_type) for s in substance.synonyms}


class TestBackfillSurvivesReprojection:
    def test_backfill_rows_are_left_alone(self):
        """(a) The NCIS projection replaces ko/en; H2SO4 and 황산 MSDS names stay."""
        substance = _substance(
            ("황산", SynonymType.KO),
            ("Sulfuric acid", SynonymType.EN),
            ("H2SO4", SynonymType.FORMULA),
            ("Oil of vitriol", SynonymType.COMMON_NAME),
            ("SULFURIC ACID 98%", SynonymType.MSDS_TITLE),
        )
        terms = extract_facts(
            {"cas_number": "7664-93-9", "name_ko": "황산", "name_en": "Sulfuric acid"}
        ).synonym_terms()

        SubstanceRepo(_FlushOnly()).replace_synonyms(
            substance, terms, owned_types=PROJECTED_SYNONYM_TYPES
        )

        assert _rows(substance) == {
            ("황산", "ko"),
            ("Sulfuric acid", "en"),
            ("H2SO4", "formula"),
            ("Oil of vitriol", "common_name"),
            ("SULFURIC ACID 98%", "msds_title"),
        }

    def test_the_projection_does_not_produce_a_backfill_type(self):
        """If it did, owning that type would hand it the backfill's rows to delete."""
        backfill = {SynonymType.MSDS_TITLE, SynonymType.COMMON_NAME, SynonymType.FORMULA}
        assert not (PROJECTED_SYNONYM_TYPES & backfill)

    def test_every_type_the_projection_derives_is_one_it_owns(self):
        """A derived type outside the owned set would never be replaced again."""
        terms = extract_facts(
            {"cas_number": "75-31-0", "name_ko": "이소프로필아민", "name_en": "Isopropylamine"}
        ).synonym_terms()
        assert {kind for _raw, _norm, kind in terms} <= PROJECTED_SYNONYM_TYPES

    def test_project_passes_its_own_types(self):
        calls: list[frozenset] = []

        class Repo:
            def upsert(self, **fields):
                return object()

            def replace_synonyms(self, substance, terms, *, owned_types):
                calls.append(frozenset(owned_types))
                return len(terms)

        project(Repo(), {"cas_number": "75-31-0", "name_en": "Isopropylamine"})
        assert calls == [PROJECTED_SYNONYM_TYPES]


class TestOwnRowsAreStillReplaced:
    def test_an_old_derived_spelling_does_not_accumulate(self):
        """(b) BR-98 - "·Isopropylamine" must not survive beside "Isopropylamine"."""
        substance = _substance(
            ("·이소프로필아민", SynonymType.KO),
            ("·Isopropylamine", SynonymType.EN),
            ("C3H9N", SynonymType.FORMULA),
        )
        terms = extract_facts(
            {"cas_number": "75-31-0", "name_ko": "·이소프로필아민", "name_en": "·Isopropylamine"}
        ).synonym_terms()

        SubstanceRepo(_FlushOnly()).replace_synonyms(
            substance, terms, owned_types=PROJECTED_SYNONYM_TYPES
        )

        assert _rows(substance) == {
            ("이소프로필아민", "ko"),
            ("Isopropylamine", "en"),
            ("C3H9N", "formula"),
        }

    def test_replacing_twice_is_idempotent(self):
        substance = _substance(("H2SO4", SynonymType.FORMULA))
        terms = extract_facts({"name_ko": "황산", "name_en": "Sulfuric acid"}).synonym_terms()
        repo = SubstanceRepo(_FlushOnly())
        repo.replace_synonyms(substance, terms, owned_types=PROJECTED_SYNONYM_TYPES)
        repo.replace_synonyms(substance, terms, owned_types=PROJECTED_SYNONYM_TYPES)
        assert len(substance.synonyms) == 3


class TestOwnershipMustBeStated:
    def test_omitting_owned_types_is_a_type_error(self):
        """(c) No default: "all types" is the accident, and a guess is someone's rows."""
        substance = _substance(("H2SO4", SynonymType.FORMULA))
        with pytest.raises(TypeError):
            SubstanceRepo(_FlushOnly()).replace_synonyms(substance, [])  # type: ignore[call-arg]
        assert _rows(substance) == {("H2SO4", "formula")}

    def test_an_empty_owned_set_is_refused(self):
        substance = _substance(("H2SO4", SynonymType.FORMULA))
        with pytest.raises(ValueError, match="at least one"):
            SubstanceRepo(_FlushOnly()).replace_synonyms(substance, [], owned_types=())
        assert _rows(substance) == {("H2SO4", "formula")}

    def test_a_term_outside_the_owned_types_is_refused_before_anything_is_deleted(self):
        substance = _substance(("황산", SynonymType.KO), ("H2SO4", SynonymType.FORMULA))
        with pytest.raises(ValueError, match="outside owned_types"):
            SubstanceRepo(_FlushOnly()).replace_synonyms(
                substance,
                [("H2SO4", "h2so4", SynonymType.FORMULA)],
                owned_types={SynonymType.KO},
            )
        assert _rows(substance) == {("황산", "ko"), ("H2SO4", "formula")}


class TestKeySupportNotice:
    """(e) Aliases work where the data exists, and not everywhere."""

    @pytest.mark.parametrize(
        ("substances", "with_alias", "expected"),
        [(49, 0, "unsupported"), (49, 13, "partial"), (49, 49, None), (0, 0, "unsupported")],
    )
    def test_alias_state_is_counted(self, substances, with_alias, expected):
        assert classify_alias(substances, with_alias) == expected

    def test_lookup_counts_the_table(self):
        class Session:
            def __init__(self, values):
                self._values = list(values)

            def scalar(self, _stmt):
                return self._values.pop(0)

        assert SubstanceLookup(Session([49, 13])).key_support() == KeySupport(
            unsupported=("un",), partial=("alias",)
        )
        assert SubstanceLookup(Session([49, 0])).key_support() == KeySupport(
            unsupported=("un", "alias"), partial=()
        )

    def test_every_alias_type_is_counted(self):
        assert ALIAS_SYNONYM_TYPES >= {
            SynonymType.ALIAS,
            SynonymType.MSDS_TITLE,
            SynonymType.COMMON_NAME,
            SynonymType.FORMULA,
        }
        assert not (ALIAS_SYNONYM_TYPES & PROJECTED_SYNONYM_TYPES)

    @staticmethod
    def _render(unsupported, partial) -> str:
        # Same device as the arq skip in test_live_contract_regressions: jinja2
        # is an app-container dependency, not a host one.
        pytest.importorskip("jinja2", reason="app-container dependency (NFR-28)")
        from app.web.routers.substances import KEY_TOPIC, MATCH_LABEL, templates

        html = templates.env.get_template("substances.html").render(
            active="substances", user=None, is_admin=False, query="", searched=False,
            matches=[], unsupported_keys=list(unsupported), partial_keys=list(partial),
            key_topic=KEY_TOPIC, match_label=MATCH_LABEL,
        )
        notice = re.search(r'data-testid="supported-keys">(.*?)</p>', html, re.S).group(1)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", notice)).strip()

    def test_partial_alias_support_is_said_as_partial(self):
        text = self._render(("un",), ("alias",))
        assert "검색 가능: 국문명 · 영문명 · CAS 번호 · 이명(異名)" in text
        assert "이명(異名)은 일부 물질에만 등록되어 있습니다." in text
        assert "이명(異名)은 현재 데이터가 없습니다" not in text
        assert "UN 번호는 현재 데이터가 없습니다." in text

    def test_no_count_is_written_into_the_notice(self):
        """A number in the sentence is false the day an alias is added (D10)."""
        assert not re.search(r"\d+\s*종", self._render(("un",), ("alias",)))

    def test_no_alias_data_still_says_no_data(self):
        text = self._render(("un", "alias"), ())
        assert "· 이명" not in text
        assert "이명(異名)은 현재 데이터가 없습니다." in text
        assert "일부 물질" not in text
