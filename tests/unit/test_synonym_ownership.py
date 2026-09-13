"""Several producers write `substance_synonym`; each replaces only the rows it owns.

`replace_synonyms()` used to clear every row of a substance and put back what the
NCIS projection derives. After D11 added 45 MSDS names, the next re-index of
`ncis_substance` would have deleted all of them without a word. Owning by type
fixed that between producers (2026-09-13 morning).

It did not fix it between documents. 황산 has two MSDS documents, and a
re-index of one that replaced every `common_name` of the substance would delete
what the other printed. So an MSDS name is owned by the document that printed
it (`source_document_id`), and the ko/en rows the projection mirrors from the
substance row are owned by the substance (NULL document).

BR-98 still holds for every owner's own rows: a change in how a name is derived
must replace the old spelling, not sit beside it (2026-08-26, 160 rows instead
of 80). Pinned here without a database.
"""

from __future__ import annotations

import re

import pytest

from app.core.types import SynonymType
from app.db.models import Substance, SubstanceSynonym
from app.db.repositories.catalog import SubstanceRepo
from app.substances.lookup import ALIAS_SYNONYM_TYPES, KeySupport, SubstanceLookup, classify_alias
from app.substances.msds_synonyms import MSDS_SYNONYM_TYPES
from app.substances.projection import (
    PROJECTED_SOURCE_DOCUMENT,
    PROJECTED_SYNONYM_TYPES,
    extract_facts,
    project,
)

# 황산's two MSDS documents in the corpus: 남해화학 and 코리아케미칼.
NAMHAE, KOREACHEM = 20, 21


class _FlushOnly:
    def flush(self) -> None:
        pass


def _substance(*rows: tuple) -> Substance:
    """rows: (term, type) for substance-owned rows, (term, type, document) otherwise."""
    substance = Substance(cas_number="7664-93-9", name_ko="황산", name_en="Sulfuric acid")
    for term, kind, *owner in rows:
        substance.synonyms.append(
            SubstanceSynonym(
                term=term,
                normalized_term=term.lower(),
                term_type=kind.value,
                source_document_id=owner[0] if owner else None,
            )
        )
    return substance


def _rows(substance: Substance) -> set[tuple]:
    return {(s.term, s.term_type, s.source_document_id) for s in substance.synonyms}


def _msds_terms(*pairs: tuple[str, SynonymType]) -> list[tuple[str, str, SynonymType]]:
    return [(term, term.lower(), kind) for term, kind in pairs]


class TestAnotherDocumentsNamesSurvive:
    """The accident this ownership exists to stop, one level below producers."""

    def test_reindexing_one_msds_keeps_the_other_msds_names(self):
        substance = _substance(
            ("황산", SynonymType.KO),
            ("H2SO4", SynonymType.FORMULA, KOREACHEM),
            ("Oil of vitriol", SynonymType.COMMON_NAME, KOREACHEM),
            ("Vitriol brown oil", SynonymType.COMMON_NAME, NAMHAE),
        )

        SubstanceRepo(_FlushOnly()).replace_synonyms(
            substance,
            _msds_terms(("Hydrogen sulfate", SynonymType.COMMON_NAME)),
            owned_types=MSDS_SYNONYM_TYPES,
            source_document_id=NAMHAE,
        )

        assert _rows(substance) == {
            ("황산", "ko", None),
            ("H2SO4", "formula", KOREACHEM),
            ("Oil of vitriol", "common_name", KOREACHEM),
            ("Hydrogen sulfate", "common_name", NAMHAE),
        }

    def test_two_documents_printing_one_name_each_keep_a_row(self):
        """Either document's re-index must leave the other's evidence standing."""
        substance = _substance(("H2SO4", SynonymType.FORMULA, KOREACHEM))
        repo = SubstanceRepo(_FlushOnly())
        repo.replace_synonyms(
            substance,
            _msds_terms(("H2SO4", SynonymType.FORMULA)),
            owned_types=MSDS_SYNONYM_TYPES,
            source_document_id=NAMHAE,
        )
        assert _rows(substance) == {
            ("H2SO4", "formula", KOREACHEM),
            ("H2SO4", "formula", NAMHAE),
        }
        repo.replace_synonyms(
            substance, [], owned_types=MSDS_SYNONYM_TYPES, source_document_id=KOREACHEM
        )
        assert _rows(substance) == {("H2SO4", "formula", NAMHAE)}

    def test_a_document_whose_subject_changed_leaves_nothing_on_the_old_one(self):
        """`replace_document_synonyms` clears rows on substances it no longer names."""
        old = _substance(
            ("Oil of vitriol", SynonymType.COMMON_NAME, NAMHAE),
            ("H2SO4", SynonymType.FORMULA, KOREACHEM),
        )
        stale = [s for s in old.synonyms if s.source_document_id == NAMHAE]

        class Session(_FlushOnly):
            def scalars(self, _stmt):
                class Result:
                    @staticmethod
                    def all():
                        return stale

                return Result()

        SubstanceRepo(Session()).replace_document_synonyms(
            NAMHAE, [], owned_types=MSDS_SYNONYM_TYPES
        )
        assert _rows(old) == {("H2SO4", "formula", KOREACHEM)}


class TestProjectionLeavesDocumentNamesAlone:
    def test_msds_rows_are_left_alone(self):
        """The NCIS projection replaces ko/en; H2SO4 and the MSDS names stay."""
        substance = _substance(
            ("황산", SynonymType.KO),
            ("Sulfuric acid", SynonymType.EN),
            ("H2SO4", SynonymType.FORMULA, KOREACHEM),
            ("Oil of vitriol", SynonymType.COMMON_NAME, KOREACHEM),
            ("SULFURIC ACID 98%", SynonymType.MSDS_TITLE, NAMHAE),
        )
        terms = extract_facts(
            {"cas_number": "7664-93-9", "name_ko": "황산", "name_en": "Sulfuric acid"}
        ).synonym_terms()

        SubstanceRepo(_FlushOnly()).replace_synonyms(
            substance,
            terms,
            owned_types=PROJECTED_SYNONYM_TYPES,
            source_document_id=PROJECTED_SOURCE_DOCUMENT,
        )

        assert _rows(substance) == {
            ("황산", "ko", None),
            ("Sulfuric acid", "en", None),
            ("H2SO4", "formula", KOREACHEM),
            ("Oil of vitriol", "common_name", KOREACHEM),
            ("SULFURIC ACID 98%", "msds_title", NAMHAE),
        }

    def test_an_msds_document_never_touches_the_substance_owned_names(self):
        substance = _substance(("황산", SynonymType.KO), ("Sulfuric acid", SynonymType.EN))
        SubstanceRepo(_FlushOnly()).replace_synonyms(
            substance, [], owned_types=MSDS_SYNONYM_TYPES, source_document_id=NAMHAE
        )
        assert _rows(substance) == {("황산", "ko", None), ("Sulfuric acid", "en", None)}

    def test_the_projection_and_msds_documents_own_disjoint_types(self):
        """If they shared one, owning it would hand one the other's rows to delete."""
        assert not (PROJECTED_SYNONYM_TYPES & MSDS_SYNONYM_TYPES)

    def test_every_type_the_projection_derives_is_one_it_owns(self):
        """A derived type outside the owned set would never be replaced again."""
        terms = extract_facts(
            {"cas_number": "75-31-0", "name_ko": "이소프로필아민", "name_en": "Isopropylamine"}
        ).synonym_terms()
        assert {kind for _raw, _norm, kind in terms} <= PROJECTED_SYNONYM_TYPES

    def test_project_passes_its_own_types_and_the_substance_owner(self):
        calls: list[tuple] = []

        class Repo:
            def upsert(self, **fields):
                return object()

            def replace_synonyms(self, substance, terms, *, owned_types, source_document_id):
                calls.append((frozenset(owned_types), source_document_id))
                return len(terms)

        project(Repo(), {"cas_number": "75-31-0", "name_en": "Isopropylamine"})
        assert calls == [(PROJECTED_SYNONYM_TYPES, None)]


class TestOwnRowsAreStillReplaced:
    def test_an_old_derived_spelling_does_not_accumulate(self):
        """BR-98 - "·Isopropylamine" must not survive beside "Isopropylamine"."""
        substance = _substance(
            ("·이소프로필아민", SynonymType.KO),
            ("·Isopropylamine", SynonymType.EN),
            ("C3H9N", SynonymType.FORMULA, KOREACHEM),
        )
        terms = extract_facts(
            {"cas_number": "75-31-0", "name_ko": "·이소프로필아민", "name_en": "·Isopropylamine"}
        ).synonym_terms()

        SubstanceRepo(_FlushOnly()).replace_synonyms(
            substance, terms, owned_types=PROJECTED_SYNONYM_TYPES, source_document_id=None
        )

        assert _rows(substance) == {
            ("이소프로필아민", "ko", None),
            ("Isopropylamine", "en", None),
            ("C3H9N", "formula", KOREACHEM),
        }

    def test_an_msds_documents_old_name_does_not_accumulate(self):
        substance = _substance(("Oil of vitriol.", SynonymType.COMMON_NAME, NAMHAE))
        SubstanceRepo(_FlushOnly()).replace_synonyms(
            substance,
            _msds_terms(("Oil of vitriol", SynonymType.COMMON_NAME)),
            owned_types=MSDS_SYNONYM_TYPES,
            source_document_id=NAMHAE,
        )
        assert _rows(substance) == {("Oil of vitriol", "common_name", NAMHAE)}

    def test_replacing_twice_is_idempotent(self):
        substance = _substance(("H2SO4", SynonymType.FORMULA, KOREACHEM))
        terms = extract_facts({"name_ko": "황산", "name_en": "Sulfuric acid"}).synonym_terms()
        repo = SubstanceRepo(_FlushOnly())
        for _ in range(2):
            repo.replace_synonyms(
                substance, terms, owned_types=PROJECTED_SYNONYM_TYPES, source_document_id=None
            )
        assert len(substance.synonyms) == 3


class TestOwnershipMustBeStated:
    def test_omitting_owned_types_is_a_type_error(self):
        """No default: "all types" is the accident, and a guess is someone's rows."""
        substance = _substance(("H2SO4", SynonymType.FORMULA, KOREACHEM))
        with pytest.raises(TypeError):
            SubstanceRepo(_FlushOnly()).replace_synonyms(  # type: ignore[call-arg]
                substance, [], source_document_id=KOREACHEM
            )
        assert _rows(substance) == {("H2SO4", "formula", KOREACHEM)}

    def test_omitting_the_document_is_a_type_error(self):
        """No default: None would hand an MSDS caller the projection's rows."""
        substance = _substance(("황산", SynonymType.KO))
        with pytest.raises(TypeError):
            SubstanceRepo(_FlushOnly()).replace_synonyms(  # type: ignore[call-arg]
                substance, [], owned_types=PROJECTED_SYNONYM_TYPES
            )
        assert _rows(substance) == {("황산", "ko", None)}

    def test_an_empty_owned_set_is_refused(self):
        substance = _substance(("H2SO4", SynonymType.FORMULA, KOREACHEM))
        with pytest.raises(ValueError, match="at least one"):
            SubstanceRepo(_FlushOnly()).replace_synonyms(
                substance, [], owned_types=(), source_document_id=KOREACHEM
            )
        assert _rows(substance) == {("H2SO4", "formula", KOREACHEM)}

    def test_a_term_outside_the_owned_types_is_refused_before_anything_is_deleted(self):
        substance = _substance(("황산", SynonymType.KO), ("H2SO4", SynonymType.FORMULA, KOREACHEM))
        with pytest.raises(ValueError, match="outside owned_types"):
            SubstanceRepo(_FlushOnly()).replace_synonyms(
                substance,
                [("H2SO4", "h2so4", SynonymType.FORMULA)],
                owned_types={SynonymType.KO},
                source_document_id=None,
            )
        assert _rows(substance) == {("황산", "ko", None), ("H2SO4", "formula", KOREACHEM)}


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
