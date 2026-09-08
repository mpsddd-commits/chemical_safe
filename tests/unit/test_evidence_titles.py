"""Every collected document reaches the generator with a name — C13, 2026-09-08.

`assembler.for_answer` renders `document.title` as the `title=` attribute of each
evidence block, and that attribute is the only thing telling the generator whose
evidence it is holding. Measured before this: substance 49/49, incident 12/12 and
law 9/9 had none, and sub-06 refused to answer because five untitled
`substance_eye` chunks were indistinguishable.

`indexing_service.process` sets `document.title` from `ref.extra["title"]`, so
these tests hold the three adapters to filling it. A backfill repairs the rows
already stored; without these the next collection empties them again.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.adapters.sources import build_adapter, load_source_specs
from app.core.document_titles import incident_title, law_title, substance_title

SUBSTANCE_ROW = {
    "dataNo": "1",
    "casNo": "7664-41-7",
    "chemKo": "암모니아",
    "chemEn": "Ammonia",
    "eyeball": "·눈에 소량은 영구적은 손상을 일으킬 것임",
}

INCIDENT_ROW = {
    "dataNo": "2025-155",
    "cscDe": "2025-12-26",
    "cscTy": "폭발",
    "area": "서울특별시 노원구",
    "place": "광운대학교",
    "chem": "폐산(지정폐기물)",
    "summary": "실험 중 산 폐액용기에 아세톤을 폐기하는 과정에서 반응하여 폭발",
}

LAW_ROW = {
    "법령ID": "004390",
    "법령명한글": "화학물질관리법 시행령",
    "시행일자": "20251001",
    "공포일자": "20251001",
}


def _spec(source_id: str) -> dict:
    spec = next((s for s in load_source_specs() if s["source_id"] == source_id), None)
    assert spec is not None, f"{source_id} missing from config/sources.yaml"
    return spec


@pytest.fixture
def keyed_settings(settings):
    return settings.model_copy(
        update={
            "ncis_api_key": SecretStr("ncis-key"),
            "law_api_key": SecretStr("law-oc"),
            "incident_api_key": SecretStr("incident-key"),
        }
    )


def _dataset_pages(row: dict) -> callable:
    """data.go.kr listing: one row on page 1, exhausted on page 2."""
    pages = {1: [row]}

    def _get(_path: str, params: dict) -> dict:
        return {"response": {"body": {"items": {"item": pages.get(params["pageNo"], [])}}}}

    return _get


class TestAdaptersNameTheirDocuments:
    def test_substance_ref_carries_name_and_cas(self, keyed_settings):
        adapter = build_adapter(_spec("ncis_substance"), keyed_settings)
        adapter._get = _dataset_pages(SUBSTANCE_ROW)
        ref = next(iter(adapter.list_targets(None)))
        assert ref.extra["title"] == "암모니아 (Ammonia) · CAS 7664-41-7"

    def test_incident_ref_carries_place_type_and_date(self, keyed_settings):
        adapter = build_adapter(_spec("incident_data"), keyed_settings)
        adapter._get = _dataset_pages(INCIDENT_ROW)
        ref = next(iter(adapter.list_targets(None)))
        assert ref.extra["title"] == "광운대학교 폭발 (2025-12-26)"

    def test_law_ref_carries_the_statutes_own_name(self, keyed_settings):
        adapter = build_adapter(_spec("law_api"), keyed_settings)
        adapter._get = lambda path, params: {"LawSearch": {"law": [LAW_ROW]}}  # noqa: ARG005
        ref = next(iter(adapter.list_targets(None)))
        assert ref.extra["title"] == "화학물질관리법 시행령"

    def test_law_title_is_not_the_search_term(self, keyed_settings):
        """`law_name` is what was searched for; three statutes share one query.

        Titling by `law_name` would make 화학물질관리법, its 시행령 and its
        시행규칙 identical in the prompt — the failure this fixes.
        """
        adapter = build_adapter(_spec("law_api"), keyed_settings)
        adapter._get = lambda path, params: {"LawSearch": {"law": [LAW_ROW]}}  # noqa: ARG005
        ref = next(iter(adapter.list_targets(None)))
        assert ref.extra["law_name"] == "화학물질관리법"
        assert ref.extra["title"] != ref.extra["law_name"]

    def test_law_title_survives_the_detail_spelling(self, keyed_settings):
        """`lawSearch.do` says `법령명한글`; `lawService.do` says `법령명_한글`."""
        adapter = build_adapter(_spec("law_api"), keyed_settings)
        row = {"법령ID": "000162", "법령명_한글": "화학물질관리법"}
        adapter._get = lambda path, params: {"LawSearch": {"law": [row]}}  # noqa: ARG005
        ref = next(iter(adapter.list_targets(None)))
        assert ref.extra["title"] == "화학물질관리법"


class TestTitleFormats:
    """A missing part shrinks the title; it never renders as `None` or `()`."""

    def test_substance_full_form(self):
        assert substance_title("암모니아", "Ammonia", "7664-41-7") == (
            "암모니아 (Ammonia) · CAS 7664-41-7"
        )

    @pytest.mark.parametrize(
        ("args", "expected"),
        [
            (("암모니아", None, "7664-41-7"), "암모니아 · CAS 7664-41-7"),
            ((None, "Ammonia", "7664-41-7"), "Ammonia · CAS 7664-41-7"),
            (("암모니아", "Ammonia", None), "암모니아 (Ammonia)"),
            ((None, None, "7664-41-7"), "CAS 7664-41-7"),
            ((None, None, None), None),
            (("  ", "", "   "), None),
        ],
    )
    def test_substance_degrades(self, args, expected):
        assert substance_title(*args) == expected

    def test_incident_falls_back_to_area(self):
        assert incident_title(None, "누출", "2025-12-01", area="경상남도 창원시") == (
            "경상남도 창원시 누출 (2025-12-01)"
        )

    def test_incident_without_a_location_still_names_the_event(self):
        assert incident_title(None, "폭발", "2025-12-26") == "폭발 (2025-12-26)"

    def test_incident_with_only_a_date_has_no_title(self):
        """`(2025-12-26)` alone names nothing, so blank is the honest answer."""
        assert incident_title(None, None, "2025-12-26") is None

    def test_law_title_trims_and_blanks(self):
        assert law_title("  화학물질관리법 시행규칙 ") == "화학물질관리법 시행규칙"
        assert law_title("   ") is None
        assert law_title(None) is None
