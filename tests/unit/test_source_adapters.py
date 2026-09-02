"""Source adapter contracts — FR-1~3, BR-02, BR-25, BR-26, BR-41, BR-42.

These are regression guards for a set of defects found when the real public API
contracts were finally obtained. Every one of them was invisible without an
issued key, which is exactly the failure mode risk R-1 predicted: the adapters
were written against assumed contracts and the assumptions were wrong.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.adapters.sources import build_adapter, load_source_specs
from app.adapters.sources.api_sources import (
    ConfiguredApiAdapter,
    _dig,
    raise_for_service_error,
)
from app.adapters.sources.http import HttpSourceClient
from app.core.errors import ApiKeyMissingError, SchemaMismatchError, SourceUnavailableError
from app.core.types import DocType

# One row exactly as 화학사고정보 (data.go.kr 15072446) documents it.
INCIDENT_ROW = {
    "dataNo": "5910",
    "cscDe": "2024-03-11",
    "cscTy": "누출",
    "area": "경기도",
    "place": "화성시 소재 화학공장",
    "chem": "황산",
    "cause": "저장탱크 배관 이음부 부식",
    "summary": "저장탱크에서 황산이 누출되어\n작업자 2명이 화학화상을 입었다.",
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


class TestAuthParameterName:
    """The credential does not go in the same parameter at every source.

    Hardcoding `serviceKey` meant 국가법령정보 received an unauthenticated
    request no matter what key was configured, and the 화학사고 service is
    documented with a capital S. Because the name is config, a source that gets
    this wrong is a one-line correction — but only if nothing reintroduces a
    constant, which is what this test pins.
    """

    @pytest.mark.parametrize(
        ("source_id", "expected"),
        [
            ("ncis_substance", "ServiceKey"),
            ("law_api", "OC"),
            ("incident_data", "ServiceKey"),
        ],
    )
    def test_configured_parameter_carries_the_credential(
        self, source_id, expected, keyed_settings
    ):
        adapter = build_adapter(_spec(source_id), keyed_settings)
        params = adapter._auth_params()
        assert list(params) == [expected]
        assert params[expected]

    def test_missing_key_fails_only_this_source(self, settings):
        """BR-02 — the error names the variable the operator has to set.

        The key is cleared explicitly: `Settings` still reads `.env`, so once a
        developer configures a real key this test would otherwise pass or fail
        depending on whose machine it runs on.
        """
        unkeyed = settings.model_copy(update={"incident_api_key": SecretStr("")})
        adapter = build_adapter(_spec("incident_data"), unkeyed)
        with pytest.raises(ApiKeyMissingError) as exc:
            adapter._auth_params()
        assert "INCIDENT_API_KEY" in str(exc.value)


class TestIncidentEndpointIsReachable:
    """The originally configured endpoint did not exist.

    `1480523/ChemicalAccidentService` is not a published service, so no issued
    key could ever have worked against it and the failure looked like a bad key.
    The real service lives in the 1480802 namespace and answers the whole record
    from its list operation.
    """

    def test_points_at_the_published_service(self):
        spec = _spec("incident_data")
        assert spec["base_url"] == "https://apis.data.go.kr/1480802/iciscsc"
        assert spec["list_path"] == "/csclist"

    def test_declares_no_detail_call(self):
        assert "detail_path" not in _spec("incident_data")

    def test_fetch_issues_no_second_request(self, keyed_settings):
        from app.core.types import SourceRef

        adapter = build_adapter(_spec("incident_data"), keyed_settings)
        adapter._client = None  # any network use would raise AttributeError
        ref = SourceRef(
            source_id="incident_data",
            external_id="5910",
            url="https://example.test/x",
            extra={"row": INCIDENT_ROW},
        )
        raw = adapter.fetch(ref)
        assert raw.payload["summary"].startswith("저장탱크에서")

    def test_url_template_produces_a_traceable_url(self, keyed_settings):
        """BR-32 — the record number identifies the row within its dataset."""
        adapter = build_adapter(_spec("incident_data"), keyed_settings)
        url = adapter._url_for("5910")
        assert url.startswith("https://www.data.go.kr/data/15072446/")
        assert "5910" in url


class TestResponseEnvelope:
    """data.go.kr nests rows deeper than the original two-level peek reached."""

    def test_dig_walks_the_standard_envelope(self):
        payload = {
            "response": {
                "header": {"resultCode": "00"},
                "body": {"items": {"item": [INCIDENT_ROW]}, "totalCount": 1},
            }
        }
        assert _dig(payload, "item") == [INCIDENT_ROW]

    def test_rows_unwraps_items_item(self, keyed_settings):
        adapter = build_adapter(_spec("incident_data"), keyed_settings)
        payload = {"response": {"body": {"items": {"item": [INCIDENT_ROW]}}}}
        assert adapter._rows(payload) == [INCIDENT_ROW]

    def test_a_single_row_is_not_a_special_case(self, keyed_settings):
        adapter = build_adapter(_spec("incident_data"), keyed_settings)
        payload = {"response": {"body": {"items": {"item": INCIDENT_ROW}}}}
        assert adapter._rows(payload) == [INCIDENT_ROW]

    def test_unrecognised_shape_is_a_schema_mismatch(self, keyed_settings):
        adapter = build_adapter(_spec("incident_data"), keyed_settings)
        with pytest.raises(SchemaMismatchError):
            adapter._rows({"response": {"body": {"totalCount": 0}}})


class TestXmlResponses:
    """These services answer in XML unless asked otherwise, and this one has no
    format parameter to ask with. Rejecting XML made a valid key look broken."""

    def test_xml_body_reads_like_json(self):
        body = """<?xml version="1.0" encoding="UTF-8"?>
        <response><header><resultCode>00</resultCode></header>
        <body><items>
          <item><dataNo>5910</dataNo><chem>황산</chem></item>
          <item><dataNo>5911</dataNo><chem>염산</chem></item>
        </items></body></response>"""
        payload = HttpSourceClient._xml_to_dict(body, "/csclist")
        assert _dig(payload, "resultCode") == "00"
        rows = _dig(payload, "item")
        assert [row["chem"] for row in rows] == ["황산", "염산"]

    def test_single_xml_item_stays_a_dict(self):
        body = "<response><body><items><item><dataNo>1</dataNo></item></items></body></response>"
        payload = HttpSourceClient._xml_to_dict(body, "/csclist")
        assert _dig(payload, "item") == {"dataNo": "1"}

    def test_malformed_xml_is_permanent(self):
        with pytest.raises(SchemaMismatchError):
            HttpSourceClient._xml_to_dict("<response><body></response>", "/csclist")


class TestServiceErrorEnvelope:
    """An unusable credential arrives as HTTP 200 with an error body.

    Reported as "no item list in response" it was indistinguishable from a
    schema change; the operator needs to be told the key is unregistered.
    """

    @pytest.mark.parametrize("code", ["20", "30", "31", "32"])
    def test_credential_failures_are_permanent_and_name_the_variable(self, code):
        payload = {"response": {"header": {"resultCode": code, "resultMsg": "ERR"}}}
        with pytest.raises(ApiKeyMissingError) as exc:
            raise_for_service_error(payload, "incident_data", "INCIDENT_API_KEY")
        assert "INCIDENT_API_KEY" in str(exc.value.detail)

    def test_quota_breach_is_transient(self):
        """BR-41 — tomorrow the same request succeeds, so it is worth retrying."""
        payload = {"resultCode": "22", "resultMsg": "LIMITED"}
        with pytest.raises(SourceUnavailableError):
            raise_for_service_error(payload, "incident_data", "INCIDENT_API_KEY")

    def test_xml_error_envelope_is_recognised(self):
        body = (
            "<OpenAPI_ServiceResponse><cmmMsgHeader>"
            "<returnReasonCode>30</returnReasonCode>"
            "<returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>"
            "</cmmMsgHeader></OpenAPI_ServiceResponse>"
        )
        payload = HttpSourceClient._xml_to_dict(body, "/csclist")
        with pytest.raises(ApiKeyMissingError):
            raise_for_service_error(payload, "incident_data", "INCIDENT_API_KEY")

    def test_success_code_passes_through(self):
        raise_for_service_error(
            {"response": {"header": {"resultCode": "00"}}}, "incident_data", "INCIDENT_API_KEY"
        )

    def test_absent_result_code_is_not_treated_as_failure(self):
        raise_for_service_error({"items": []}, "law_api", "LAW_API_KEY")


class TestFieldProjection:
    def test_vendor_names_become_logical_names(self, keyed_settings):
        adapter = build_adapter(_spec("incident_data"), keyed_settings)
        projected = adapter._project(INCIDENT_ROW)
        assert projected["occurred_at"] == "2024-03-11"
        assert projected["substances"] == "황산"
        assert projected["cause"].startswith("저장탱크")
        assert "cscDe" not in projected

    def test_unmapped_fields_are_kept(self, keyed_settings):
        adapter = build_adapter(_spec("incident_data"), keyed_settings)
        projected = adapter._project({**INCIDENT_ROW, "unexpectedField": "값"})
        assert projected["unexpectedField"] == "값"

    def test_external_id_does_not_shadow_a_better_name(self, keyed_settings):
        """When `external_id` aliases a field that has a substantive name, the
        substantive name wins — otherwise a CAS number would be rendered as
        `external_id` and never recognised.

        Built from a literal spec rather than a live source: this is a property
        of `_project`, and it should not start passing vacuously the day a
        source's field map stops aliasing anything.
        """
        spec = {
            "source_id": "ncis_substance",
            "base_url": "https://example.test",
            "doc_type": "msds",
            "field_map": {"external_id": "casNo", "cas_number": "casNo", "name_ko": "chemKo"},
        }
        adapter = build_adapter({**_spec("ncis_substance"), **spec}, keyed_settings)
        projected = adapter._project({"casNo": "7664-93-9", "chemKo": "황산"})
        assert projected["cas_number"] == "7664-93-9"
        assert projected["name_ko"] == "황산"


class TestIncidentRecordSurvivesToAChunk:
    """The end-to-end guard for the defect that mattered most.

    `summary` is the only prose in an accident record. It was not a label the
    structurer knew, and text outside a section is never chunked (BR-26), so the
    record would have been indexed with its substance silently missing — and u2
    would have answered accident questions from a corpus that did not contain
    the accidents.
    """

    def _chunks(self, settings, row):
        from app.core.types import ChunkMeta, RawDocument, SourceRef
        from app.processing.runner import PipelineRunner

        adapter = build_adapter(_spec("incident_data"), settings)
        ref = SourceRef(
            source_id="incident_data",
            external_id="5910",
            url="https://www.data.go.kr/data/15072446/openapi.do#dataNo=5910",
            extra={"row": row},
        )
        raw = RawDocument(
            ref=ref,
            payload=adapter._project(row),
            media_type="application/json",
            stored_path="/tmp/incident.json",
        )
        meta = ChunkMeta(doc_type="incident", source_url=ref.url)
        return PipelineRunner(settings).run(raw, DocType.INCIDENT, meta).chunks

    def test_summary_reaches_a_chunk(self, keyed_settings):
        chunks = self._chunks(keyed_settings, INCIDENT_ROW)
        assert any("화학화상" in c.text for c in chunks), "accident summary was dropped"

    def test_summary_is_not_truncated_at_its_first_newline(self, keyed_settings):
        chunks = self._chunks(keyed_settings, INCIDENT_ROW)
        summary = next(c for c in chunks if "저장탱크에서 황산이" in c.text)
        assert "작업자 2명이 화학화상을 입었다." in summary.text

    def test_every_populated_field_is_covered_by_some_chunk(self, keyed_settings):
        chunks = self._chunks(keyed_settings, INCIDENT_ROW)
        body = "\n".join(c.text for c in chunks)
        for value in ("누출", "경기도", "화성시", "황산", "부식"):
            assert value in body, f"{value!r} fell outside every chunk"

    def test_absent_field_still_produces_no_section(self, keyed_settings):
        """BR-25 / NFR-8 — this API reports no damage field; do not invent one."""
        chunks = self._chunks(keyed_settings, INCIDENT_ROW)
        assert not any(c.meta.section_code == "incident_damage" for c in chunks)

    def test_offsets_still_match_the_extracted_text(self, keyed_settings):
        """BR-30 — the invariant u2's citations rest on."""
        from app.core.types import ChunkMeta, RawDocument, SourceRef
        from app.processing.runner import PipelineRunner

        adapter = build_adapter(_spec("incident_data"), keyed_settings)
        ref = SourceRef(
            source_id="incident_data", external_id="5910",
            url="https://example.test/x", extra={"row": INCIDENT_ROW},
        )
        raw = RawDocument(
            ref=ref, payload=adapter._project(INCIDENT_ROW),
            media_type="application/json", stored_path="/tmp/incident.json",
        )
        meta = ChunkMeta(doc_type="incident", source_url=ref.url)
        ctx = PipelineRunner(keyed_settings).run(raw, DocType.INCIDENT, meta)
        for chunk in ctx.chunks:
            assert ctx.extracted.text[chunk.start_offset : chunk.end_offset] == chunk.text


class TestEveryConfiguredSourceStillBuilds:
    def test_all_sources_have_an_adapter(self, keyed_settings):
        for spec in load_source_specs():
            adapter = build_adapter(spec, keyed_settings)
            assert adapter.source_id() == spec["source_id"]

    def test_api_sources_declare_an_auth_parameter(self):
        """A source that needs a key must say where the key goes; the default
        was silently wrong for two of three sources."""
        for spec in load_source_specs():
            if spec.get("requires_api_key") and spec.get("kind") == "api":
                assert spec.get("auth_param"), f"{spec['source_id']} has no auth_param"

    def test_configured_adapters_expose_the_port(self, keyed_settings):
        from app.ports.source import SourceAdapter

        for spec in load_source_specs():
            assert isinstance(build_adapter(spec, keyed_settings), SourceAdapter)


class TestExtraParamsAreSent:
    def test_configured_extra_params_ride_along(self, keyed_settings):
        adapter: ConfiguredApiAdapter = build_adapter(_spec("law_api"), keyed_settings)
        params = adapter._base_params()
        assert params["OC"] == "law-oc"
        assert params["type"] == "JSON"


def _envelope(rows, total=7189):
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
            "body": {"numOfRows": 100, "pageNo": 1, "totalCount": total,
                     "items": {"item": rows}},
        }
    }


class TestListingExhaustion:
    """Past the last page data.go.kr sends `"items": ""`, not an empty list.

    Measured on page 73 of 화학물질안전관리정보 (7,189 rows at page_size 100).
    `list_targets` reads an empty return as "stop", so raising here aborts a
    full collection at the very end. Nothing had ever hit it, because
    INITIAL_SUBSTANCE_TARGET stopped the loop long before exhaustion — the
    same shape as the u1 defects above, a path that had never run.
    """

    def test_empty_string_items_means_stop(self, keyed_settings):
        adapter: ConfiguredApiAdapter = build_adapter(_spec("ncis_substance"), keyed_settings)
        payload = {
            "response": {
                "header": {"resultCode": "00"},
                "body": {"items": "", "numOfRows": 100, "pageNo": 73, "totalCount": 7189},
            }
        }
        assert adapter._rows(payload) == []

    def test_a_non_empty_string_is_still_a_schema_error(self, keyed_settings):
        """Only exhaustion is silent. Anything else is the source misbehaving."""
        adapter: ConfiguredApiAdapter = build_adapter(_spec("ncis_substance"), keyed_settings)
        payload = {"response": {"header": {"resultCode": "00"}, "body": {"items": "nonsense"}}}
        with pytest.raises(SchemaMismatchError):
            adapter._rows(payload)


class TestSubstanceSelectionInTheAdapter:
    """BR-08 — the listing is ranked before it is cut (defect 44)."""

    PAGES = {
        1: [
            {"dataNo": "1", "chemKo": "·아이소프로필아민", "chemEn": "Isopropylamine"},
            {"dataNo": "2", "chemKo": "·테트라메틸실리케이트", "chemEn": "Tetramethyl silicate"},
        ],
        2: [
            {"dataNo": "3", "chemKo": "·2-브로모톨루엔", "chemEn": "2-Bromotoluene"},
            {"dataNo": "4", "chemKo": "·톨루엔", "chemEn": "Toluene"},
        ],
    }

    def _adapter(self, settings, **overrides):
        settings = settings.model_copy(update=overrides)
        adapter = build_adapter(_spec("ncis_substance"), settings)
        adapter._get = lambda path, params: _envelope(self.PAGES.get(params["pageNo"], ""))
        return adapter

    def test_a_corpus_substance_outranks_source_order(self, keyed_settings):
        adapter = self._adapter(keyed_settings, initial_substance_target=2)
        adapter.priority_terms = ("톨루엔",)
        assert [ref.external_id for ref in adapter.list_targets(None)] == ["4", "1"]

    def test_substring_neighbours_are_not_promoted(self, keyed_settings):
        """2-브로모톨루엔 contains "톨루엔" and is a different substance."""
        adapter = self._adapter(keyed_settings, initial_substance_target=2)
        adapter.priority_terms = ("톨루엔",)
        assert "3" not in [ref.external_id for ref in adapter.list_targets(None)]

    def test_without_terms_the_old_behaviour_is_exact(self, keyed_settings):
        """No terms, no scan: the plain path must not start reading 7,189 rows."""
        adapter = self._adapter(keyed_settings, initial_substance_target=2)
        seen_pages = []
        inner = adapter._get

        def recording(path, params):
            seen_pages.append(params["pageNo"])
            return inner(path, params)

        adapter._get = recording
        assert [ref.external_id for ref in adapter.list_targets(None)] == ["1", "2"]
        assert seen_pages == [1]

    def test_scan_cap_bounds_the_ranking_pass(self, keyed_settings):
        """The cap stops a source that grows from turning collection into a scan."""
        adapter = self._adapter(keyed_settings, initial_substance_target=2, substance_scan_cap=2)
        adapter.priority_terms = ("톨루엔",)
        # Only page 1 is inside the cap, and 톨루엔 is on page 2.
        assert [ref.external_id for ref in adapter.list_targets(None)] == ["1", "2"]

    def test_english_name_is_matched_too(self, keyed_settings):
        adapter = self._adapter(keyed_settings, initial_substance_target=1)
        adapter.priority_terms = ("Toluene",)
        assert [ref.external_id for ref in adapter.list_targets(None)] == ["4"]
