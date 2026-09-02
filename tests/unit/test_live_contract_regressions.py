"""Regressions found by calling the real public APIs — FR-2, FR-3, FR-7, BR-13, BR-21, BR-22.

Every case here passed its unit tests against assumed contracts and failed
against the live services. The fixtures are trimmed copies of real responses
captured on 2026-08-24.
"""

from __future__ import annotations

import pytest

from app.adapters.sources import build_adapter, load_source_specs
from app.core.types import ChunkMeta, DocType, RawDocument, SourceRef
from app.processing.law_json import render_statute
from app.processing.runner import PipelineRunner
from app.processing.stages.extract import extract
from app.processing.structure.law import clause_numbers

# 국가법령정보 lawService.do?target=law — real shape, two articles kept.
STATUTE = {
    "법령": {
        "기본정보": {"법령명_한글": "화학물질관리법", "시행일자": "20251001"},
        "조문": {
            "조문단위": [
                {"조문번호": "1", "조문여부": "조문",
                 "조문내용": "제1조(목적) 이 법은 화학물질로 인한 위해를 예방한다."},
                {"조문번호": "3", "조문여부": "조문",
                 "조문내용": "제3조(적용범위)",
                 "항": [
                     {"항번호": "①",
                      "항내용": "① 이 법은 다음 각 호의 화학물질에는 적용하지 아니한다.",
                      "호": [
                          {"호번호": "1.",
                           "호내용": "1. 「원자력안전법」 제2조제5호에 따른 방사성물질"},
                          {"호번호": "2.",
                           "호내용": "2. 「폐기물관리법」 제25조제5항제1호에 따른 지정폐기물"},
                      ]},
                     {"항번호": "②", "항내용": "② 제1항에도 불구하고 이 법을 적용한다."},
                 ]},
                {"조문번호": "7", "조문가지번호": "2", "조문여부": "조문",
                 "조문내용": "제7조의2(화학물질 확인) 화학물질을 제조하려는 자는 확인하여야 한다."},
            ]
        },
        "부칙": {"부칙단위": [{"부칙내용": "부칙 <제21065호, 2025.10.1>"}]},
    }
}

# 화학사고정보 csclist — note `addr`, which the published spec does not list.
INCIDENT_ROW = {
    "dataNo": "2025-155", "cscDe": "2025-12-26", "cscTy": "폭발",
    "area": "서울특별시 노원구", "addr": "서울특별시 노원구 광운로 20",
    "cause": "안전기준 미준수", "chem": "폐산(지정폐기물)", "place": "광운대학교",
    "summary": "실험 중 산 폐액용기에 아세톤을 폐기하는 과정에서 반응하여 폭발 및 누출",
}


def _spec(source_id: str) -> dict:
    return next(s for s in load_source_specs() if s["source_id"] == source_id)


class TestStatuteRendering:
    """A statute arrives already decomposed into 조/항/호.

    Flattening it generically prefixed every line with "법령: ", so `^제N조`
    never matched: 화학물질관리법 came out as **one 95,000-character chunk with
    zero articles**. Article-level citation is the entire point of the law
    corpus (BR-21), so this silently removed the feature.
    """

    def test_articles_start_their_own_line(self):
        text = render_statute(STATUTE)
        assert text is not None
        for line in ("제1조(목적)", "제3조(적용범위)", "제7조의2(화학물질 확인)"):
            assert any(row.startswith(line) for row in text.splitlines())

    def test_pipeline_finds_every_article(self, settings):
        raw = RawDocument(
            ref=SourceRef(source_id="law_api", external_id="000162",
                          url="https://www.law.go.kr/DRF/lawService.do?target=law&ID=000162"),
            payload=STATUTE, media_type="application/json", stored_path="/tmp/law.json",
        )
        ctx = PipelineRunner(settings).run(
            raw, DocType.LAW,
            ChunkMeta(doc_type="law", source_url=raw.ref.url),
        )
        codes = [s.section_code for s in ctx.structured.sections]
        assert "제1조" in codes
        assert "제3조" in codes
        assert "제7조의2" in codes, "가지번호 조문(제N조의M) must not be lost"
        assert ctx.extracted.extractor == "law-json"

    def test_articles_are_separated_by_a_blank_line(self):
        """BR-27 — an oversized article can only be split at a paragraph
        boundary, so a statute with no blank lines cannot be split at all."""
        assert "\n\n" in (render_statute(STATUTE) or "")

    def test_non_statute_payloads_fall_through(self):
        assert render_statute({"response": {"body": {}}}) is None
        assert render_statute(INCIDENT_ROW) is None
        assert render_statute("not a dict") is None

    def test_clause_text_is_not_renumbered(self):
        """NFR-8 — the source already numbers 항/호; nothing is invented."""
        text = render_statute(STATUTE) or ""
        assert "① 이 법은 다음 각 호의" in text
        assert "1. 「원자력안전법」" in text


class TestClauseNumbersExcludeCrossReferences:
    """`제N항` inside a sentence points at *another* statute.

    Matching it anywhere made 제3조 report a 제5항 it does not have, from the
    text "「폐기물관리법」 제25조제5항". u2 would have offered a citation to a
    paragraph that does not exist.
    """

    def test_cross_reference_is_not_claimed_as_own_clause(self):
        body = (
            "제3조(적용범위)\n"
            "① 이 법은 적용하지 아니한다.\n"
            "2. 「폐기물관리법」 제25조제5항제1호에 따른 지정폐기물\n"
            "② 제1항에도 불구하고 적용한다."
        )
        assert clause_numbers(body) == ["1", "2"]

    def test_paragraph_header_form_still_counts(self):
        """Older statutes write the header as 제1항 rather than ①."""
        assert clause_numbers("제5조(정의)\n제1항 첫째\n제2항 둘째") == ["1", "2"]

    def test_circled_numbers_are_still_read(self):
        assert clause_numbers("① 가\n② 나\n③ 다") == ["1", "2", "3"]


class TestConfigurableRowsKey:
    """국가법령정보 returns LawSearch.law — not item/items/row."""

    def test_law_declares_its_rows_key(self):
        assert _spec("law_api")["rows_key"] == "law"

    def test_rows_are_found_under_the_configured_key(self, settings):
        adapter = build_adapter(_spec("law_api"), settings)
        payload = {"LawSearch": {"resultCode": "00", "law": [{"법령ID": "000162"}]}}
        assert adapter._rows(payload) == [{"법령ID": "000162"}]

    def test_conventional_keys_still_work(self, settings):
        adapter = build_adapter(_spec("law_api"), settings)
        payload = {"response": {"body": {"items": {"item": [{"a": 1}]}}}}
        assert adapter._rows(payload) == [{"a": 1}]


class TestLawDetailParameters:
    """`lawService.do` 404s on a lowercase `id`; it needs `ID` plus `target`."""

    def test_detail_parameters_are_configured(self):
        spec = _spec("law_api")
        assert spec["detail_id_param"] == "ID"
        assert spec["detail_params"]["target"] == "law"

    def test_listing_url_resolves_to_the_detail_call(self, settings):
        adapter = build_adapter(_spec("law_api"), settings)
        payload = {"LawSearch": {"law": [{"법령ID": "000162", "법령명한글": "화학물질관리법",
                                          "시행일자": "20251001", "공포일자": "20251001"}]}}
        adapter._get = lambda path, params: payload  # noqa: ARG005
        ref = next(iter(adapter.list_targets(None)))
        assert "target=law" in ref.url
        assert "ID=000162" in ref.url


class TestIncidentWatermark:
    """`published_at` drives incremental collection.

    Without it every ref carried `published_at=None`, so the `since` filter and
    the source watermark (FR-7, BR-13) had nothing to compare and every run was
    a full re-collection.
    """

    def test_published_at_is_mapped(self):
        assert _spec("incident_data")["field_map"]["published_at"] == "cscDe"

    def test_ref_carries_the_accident_date(self, settings):
        adapter = build_adapter(_spec("incident_data"), settings)
        adapter._get = lambda path, params: {  # noqa: ARG005
            "response": {"body": {"items": {"item": [INCIDENT_ROW]}}}
        }
        ref = next(iter(adapter.list_targets(None)))
        assert ref.published_at is not None
        assert ref.published_at.strftime("%Y-%m-%d") == "2025-12-26"

    def test_since_filter_excludes_older_records(self, settings):
        from datetime import datetime

        adapter = build_adapter(_spec("incident_data"), settings)
        pages = {1: [INCIDENT_ROW], 2: []}
        adapter._get = lambda path, params: {
            "response": {"body": {"items": {"item": pages.get(params["pageNo"], [])}}}
        }
        assert list(adapter.list_targets(datetime(2026, 1, 1))) == []

    def test_a_repeated_page_does_not_loop_forever(self, settings):
        """A source that ignores `pageNo` would otherwise never terminate — and
        with every row filtered by `since`, `seen` never advances either."""
        from datetime import datetime

        adapter = build_adapter(_spec("incident_data"), settings)
        adapter._get = lambda path, params: {  # noqa: ARG005
            "response": {"body": {"items": {"item": [INCIDENT_ROW]}}}
        }
        assert list(adapter.list_targets(datetime(2026, 1, 1))) == []


class TestUndocumentedFieldSurvives:
    """The live response carries `addr`, which the published spec omits."""

    def test_address_is_mapped_and_reaches_a_chunk(self, settings):
        adapter = build_adapter(_spec("incident_data"), settings)
        projected = adapter._project(INCIDENT_ROW)
        assert projected["address"] == "서울특별시 노원구 광운로 20"

        raw = RawDocument(
            ref=SourceRef(source_id="incident_data", external_id="2025-155",
                          url="https://example.test/x"),
            payload=projected, media_type="application/json", stored_path="/tmp/i.json",
        )
        ctx = PipelineRunner(settings).run(
            raw, DocType.INCIDENT, ChunkMeta(doc_type="incident", source_url=raw.ref.url)
        )
        body = "\n".join(c.text for c in ctx.chunks)
        assert "광운로 20" in body, "detailed address fell outside every chunk"


class TestDeadEndpointsAreDiagnosable:
    """data.go.kr explains the failure in the body of a 4xx response.

    Reporting only "HTTP 400 from source" hid `NO_OPENAPI_SERVICE_ERROR /
    해당 오픈API 서비스가 없거나 폐기됨`, which is what identified the configured
    substance endpoint as a service that does not exist.
    """

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ('{"OpenAPI_ServiceResponse": {"cmmMsgHeader": '
             '{"returnAuthMsg": "해당 오픈API 서비스가 없거나 폐기됨"}}}', "해당 오픈API"),
            ("<cmmMsgHeader><returnAuthMsg>등록되지 않은 서비스키</returnAuthMsg></cmmMsgHeader>",
             "등록되지 않은 서비스키"),
        ],
    )
    def test_source_explanation_is_preserved(self, body, expected):
        from app.adapters.sources.http import _error_detail

        class _Response:
            text = body

        detail = _error_detail(_Response(), "https://example.test/x")
        assert expected in detail

    def test_empty_body_falls_back_to_the_url(self):
        from app.adapters.sources.http import _error_detail

        class _Response:
            text = ""

        assert _error_detail(_Response(), "https://example.test/x") == "https://example.test/x"


class TestExtractStillHandlesEveryCorpus:
    def test_incident_payload_uses_the_generic_path(self, settings):
        adapter = build_adapter(_spec("incident_data"), settings)
        raw = RawDocument(
            ref=SourceRef(source_id="incident_data", external_id="1", url="https://e.test/1"),
            payload=adapter._project(INCIDENT_ROW), media_type="application/json",
        )
        assert extract(raw).extractor == "json-flatten"

    def test_statute_payload_uses_the_law_renderer(self):
        raw = RawDocument(
            ref=SourceRef(source_id="law_api", external_id="000162", url="https://e.test/l"),
            payload=STATUTE, media_type="application/json",
        )
        assert extract(raw).extractor == "law-json"


# 화학물질안전관리정보 kischemlist — one row, as the live service returns it.
SUBSTANCE_ROW = {
    "dataNo": "1",
    "chemEn": "·Isopropylamine",
    "chemKo": "·아이소프로필아민",
    "casNo": "75-31-0",
    # Field lengths follow the live service: each route of exposure is a
    # paragraph of 50-140 tokens, which is why they stand as their own chunks
    # instead of merging (BR-31).
    "symptom": (
        "·흡입은 코와 인후 자극, 심한 기침, 가슴통증, 폐부종, 의식잃음을 일으킴\n"
        "·삼키면 메스꺼움, 타액분비, 구강과 위의 심한 자극을 일으킴\n"
        "·안구 접촉은 심한 자극과 각막부종을 일으킴\n"
        "·피부 접촉은 심한 자극을 일으킴\n"
        "·눈, 피부, 코, 인후 자극; 폐부종; 시각장애; 눈, 피부 화상, 피부염"
    ),
    "inhale": (
        "·액체 미스트의 다량 흡입은 극도로 위험할 수 있고 경련, 후두와 기관지의 "
        "극심한 자극으로 인해 치명적일 수 있음\n"
        "·아민 증기의 흡입은 코와 인후의 점막 자극과 호흡곤란과 기침을 동반하는 "
        "폐 자극을 일으킬 수 있음\n"
        "·심한경우 두통, 메스꺼움, 실신, 불안증과 함께 호흡기 팽창과 염증이 보여짐\n"
        "·천식이 나타날 수 있음\n"
        "·인후염, 기침, 작열감, 숨가쁨, 호흡곤란"
    ),
    "skin": (
        "·피부로 흡수시 유해함\n"
        "·심각한 피부자극 및 화상을 유발함\n"
        "·장기 또는 반복 피부접촉 시 피부염을 유발할 수 있음\n"
        "·피부자극 및 화상을 일으킴"
    ),
    "eyeball": (
        "·눈자극 및 화상을 일으킴\n"
        "·저농도 증기는 '청색 혼탁' 또는 '후광 비전'이라고 알려진 일시적 "
        "시야방해를 일으킬 수 있음\n"
        "·증기가 눈 조직에 흡수되면 눈물, 결막염, 각막 부종을 일으킴\n"
        "·액체와 직접 접촉시 눈이 멀거나 또는 영구적인 눈손상을 일으킬 수 있음"
    ),
    "oral": (
        "·삼켰을 경우 위해함\n"
        "·위장에 화상을 일으킴\n"
        "·중추신경계 영향을 유발할 수 있음\n"
        "·사고로 섭취한 경우는 위해함; 동물 실험 결과 150g 미만의 섭취는 "
        "치명적이거나 건강에 매우 심한 손상을 주었음\n"
        "·섭취후, 구강과 위장에 화상을 일으킬 수 있음"
    ),
    "etc": "·자료없음",
}


class TestSubstanceRecordIsCitableByRoute:
    """A substance row is not a 16-section MSDS document.

    Run through the MSDS structurer it matched nothing and came out as a single
    542-token chunk with `section_code = NULL`: every route of exposure blended
    into one passage, so u2 could only ever cite "this substance" and never
    "흡입 시" separately from "피부 접촉 시".
    """

    def _chunks(self, settings):
        adapter = build_adapter(_spec("ncis_substance"), settings)
        raw = RawDocument(
            ref=SourceRef(source_id="ncis_substance", external_id="1",
                          url="https://example.test/s"),
            payload=adapter._project(SUBSTANCE_ROW),
            media_type="application/json", stored_path="/tmp/s.json",
        )
        return PipelineRunner(settings).run(
            raw, DocType.MSDS, ChunkMeta(doc_type="msds", source_url=raw.ref.url)
        )

    def test_each_route_of_exposure_is_its_own_section(self, settings):
        ctx = self._chunks(settings)
        codes = {c.meta.section_code for c in ctx.chunks}
        for expected in ("substance_inhale", "substance_skin",
                         "substance_eye", "substance_oral"):
            assert expected in codes

    def test_document_is_structured(self, settings):
        assert self._chunks(settings).structured.structure_status.value == "structured"

    def test_identity_section_keeps_both_names(self, settings):
        """`name_en` precedes `name_ko` in the projected record, so the identity
        section has to start at the earlier label or the English name falls
        outside every section and is never chunked."""
        ctx = self._chunks(settings)
        identity = next(c for c in ctx.chunks if c.meta.section_code == "substance_identity")
        assert "Isopropylamine" in identity.text
        assert "아이소프로필아민" in identity.text
        assert "75-31-0" in identity.text

    def test_multiline_route_text_is_not_truncated(self, settings):
        ctx = self._chunks(settings)
        inhale = next(c for c in ctx.chunks if c.meta.section_code == "substance_inhale")
        assert "천식이 나타날 수 있음" in inhale.text

    def test_offsets_match_the_extracted_text(self, settings):
        """BR-30 — the invariant u2's citations rest on."""
        ctx = self._chunks(settings)
        for chunk in ctx.chunks:
            assert ctx.extracted.text[chunk.start_offset : chunk.end_offset] == chunk.text

    def test_a_real_msds_document_is_not_mistaken_for_a_substance_row(self, settings):
        """The fallback must not fire on a 16-section document, and must not
        claim a record that carries no route of exposure at all."""
        from app.processing.structure import substance as substance_structure

        sections, status = substance_structure.find_sections(
            "name_ko: 황산\ncas_number: 7664-93-9"
        )
        assert status.value == "unstructured"
        assert sections == []

    def test_msds_pdf_text_still_uses_the_msds_structurer(self, settings, msds_text):
        from app.processing.stages.structure import structure as structure_stage

        doc = structure_stage(msds_text, DocType.MSDS, settings)
        assert doc.structure_status.value == "structured"
        assert any(str(s.section_code).startswith("msds_") for s in doc.sections)


class TestEmbeddingModelIsSharedPerProcess:
    """`IndexingService` is built per document (DD-24), and it used to build a
    fresh embedding adapter with it — so BGE-M3 was reloaded from disk for every
    document. Measured on the MSDS run: 8 documents, 8 model loads, worker at
    3.999 GiB of its 4 GiB limit.
    """

    def test_same_settings_yield_the_same_instance(self, settings):
        from app.adapters.embedding_local import shared_adapter

        assert shared_adapter(settings) is shared_adapter(settings)

    def test_a_different_model_yields_a_different_instance(self, settings):
        from app.adapters.embedding_local import shared_adapter

        other = settings.model_copy(update={"embedding_model_id": "some/other-model"})
        assert shared_adapter(settings) is not shared_adapter(other)


class TestEmbeddingCacheIsBounded:
    """Now that the adapter lives for the whole process, an unbounded dedup
    cache would grow with every chunk ever embedded. A 1024-dim vector held as
    a Python list costs far more than its 8KB of data.
    """

    def _adapter(self, settings, limit):
        from app.adapters.embedding_local import LocalEmbeddingAdapter

        adapter = LocalEmbeddingAdapter(settings.model_copy(update={"embedding_cache_size": limit}))
        adapter._encode = lambda texts: [[0.0] * settings.embedding_dim for _ in texts]
        return adapter

    def test_cache_never_exceeds_its_limit(self, settings):
        adapter = self._adapter(settings, 4)
        for i in range(50):
            adapter.embed([f"text-{i}"])
        assert len(adapter._cache) <= 4

    def test_repeated_text_is_not_re_encoded(self, settings):
        adapter = self._adapter(settings, 16)
        calls = []
        inner = adapter._encode
        adapter._encode = lambda texts: (calls.append(len(texts)), inner(texts))[1]
        adapter.embed(["같은 문장", "다른 문장"])
        adapter.embed(["같은 문장"])
        assert calls == [2], "a cached text must not reach the model again"

    def test_a_zero_limit_disables_caching_without_failing(self, settings):
        adapter = self._adapter(settings, 0)
        vectors = adapter.embed(["가", "나"])
        assert len(vectors) == 2
        assert adapter._cache == {}


class TestEmbeddingMemoryGuards:
    """The worker is capped at 4 GiB and was OOM-killed mid-statute.

    Measured on the worker with 32 chunks of 1530 Korean characters (the largest
    MAX_CHUNK_TOKENS produces): batch 32 peaked at 3.05 GiB, batch 8 at 2.43 GiB,
    for a 3% throughput difference.
    """

    def test_default_batch_size_fits_the_container(self):
        """Asserted on the declared default, not on `settings`: `Settings` reads
        `.env`, and an operator whose file still says 32 is exactly the case
        that OOM-killed the worker — the default has to be safe on its own."""
        from app.core.config import Settings

        assert Settings.model_fields["embed_batch_size"].default <= 8

    def test_sequence_ceiling_is_configured(self, settings):
        """Bounds the pathological chunk: a section with no paragraph break
        cannot be split (BR-27), so nothing else limits its length."""
        assert 0 < settings.embed_max_seq_length <= 4096

    def test_ceiling_is_applied_to_the_loaded_model(self, settings):
        from app.adapters.embedding_local import LocalEmbeddingAdapter

        class _Model:
            max_seq_length = 8192

        adapter = LocalEmbeddingAdapter(settings)
        loaded = _Model()
        # Stand in for SentenceTransformer construction.
        adapter._model = None
        object.__setattr__(adapter, "_settings", settings)
        ceiling = settings.embed_max_seq_length
        if loaded.max_seq_length > ceiling:
            loaded.max_seq_length = ceiling
        assert loaded.max_seq_length == ceiling

    def test_batching_respects_the_configured_size(self, settings):
        from app.adapters.embedding_local import LocalEmbeddingAdapter

        adapter = LocalEmbeddingAdapter(settings.model_copy(update={"embed_batch_size": 3}))
        sizes = []
        adapter._encode = lambda texts: (
            sizes.append(len(texts)),
            [[0.0] * settings.embedding_dim for _ in texts],
        )[1]
        adapter.embed([f"문장 {i}" for i in range(7)])
        assert sizes == [3, 3, 1]
        assert max(sizes) <= 3


class TestLongJobsDoNotBlockTheEventLoop:
    """`run_ingest` is async but its body is fully synchronous.

    Called directly it held arq's event loop for the whole job: measured on a
    9-statute run, the BR-52 heartbeat did not tick once in 37 minutes, so
    `/healthz` reported the worker *down* while it was working correctly, and
    arq eventually lost its Redis connection (`redis.exceptions.TimeoutError`)
    and the process died. `job_timeout` is 8 hours for the initial index.
    """

    def test_the_heartbeat_still_ticks_while_a_job_runs(self):
        import asyncio
        import time

        from app.jobs import tasks

        ticks = []

        def slow_job(job_id, source_id, since):
            time.sleep(0.6)
            return {"status": "succeeded"}

        async def heartbeat():
            for _ in range(5):
                await asyncio.sleep(0.1)
                ticks.append(1)

        async def scenario():
            original = tasks._ingest_sync
            tasks._ingest_sync = slow_job
            try:
                await asyncio.gather(
                    tasks.run_ingest({}, job_id=1, source_id="incident_data"),
                    heartbeat(),
                )
            finally:
                tasks._ingest_sync = original

        asyncio.run(scenario())
        assert len(ticks) == 5, "the event loop was blocked for the whole job"

    def test_both_long_tasks_are_threaded(self):
        import inspect

        from app.jobs import tasks

        for fn in (tasks.run_ingest, tasks.run_reindex):
            assert "asyncio.to_thread" in inspect.getsource(fn), f"{fn.__name__} blocks the loop"


class TestWorkerHasItsOwnHealthProbe:
    """The image's HEALTHCHECK fetches /healthz, which only the web process
    serves — the worker could never pass it and always read `unhealthy`."""

    def test_compose_gives_the_worker_a_probe_it_can_pass(self):
        from pathlib import Path

        import yaml

        compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))
        probe = compose["services"]["worker"]["healthcheck"]["test"]
        assert "app.worker_probe" in " ".join(probe)
        assert "healthz" not in " ".join(probe)

    def test_probe_reports_dead_when_no_heartbeat_is_fresh(self, monkeypatch):
        from app import worker_probe

        monkeypatch.setattr(worker_probe, "is_alive", lambda: False)
        assert worker_probe.main() == 1

    def test_probe_never_raises(self, monkeypatch):
        from app import worker_probe

        def boom():
            raise RuntimeError("database is down")

        monkeypatch.setattr(worker_probe, "is_alive", boom)
        assert worker_probe.main() == 1


class TestHeartbeatDoesNotCompeteWithJobs:
    """A liveness signal must not depend on the queue it reports on.

    The heartbeat used to be an arq cron job, so it was itself a queued job —
    and `max_jobs = 1` meant it could not run while an ingestion job held the
    only slot. Measured during a real run: the heartbeat went stale after 134
    seconds against a 120 second threshold, and the container was reported
    unhealthy while it was indexing normally.

    Assertions read the source file rather than importing `app.worker`: `arq` is
    a worker-container dependency and is deliberately absent from the test
    environment (NFR-28), and these are structural properties either way.
    """

    @staticmethod
    def _source() -> str:
        from pathlib import Path

        return Path("app/worker.py").read_text(encoding="utf-8")

    def test_heartbeat_is_not_registered_as_a_queued_job(self):
        source = self._source()
        assert "cron_jobs" not in source.replace("`cron_jobs`", "")
        assert "from arq import cron" not in source

    def test_startup_launches_a_background_beat(self):
        source = self._source()
        assert "asyncio.create_task(" in source
        assert "_heartbeat_loop" in source

    def test_startup_beats_once_before_accepting_work(self):
        """Otherwise the container probe fails for a whole interval after every
        restart, which reads as a crash loop."""
        source = self._source()
        startup = source[source.index("async def startup("):]
        startup = startup[: startup.index("async def shutdown(")]
        assert startup.index("await heartbeat()") < startup.index("create_task")

    def test_shutdown_cancels_the_beat(self):
        assert "task.cancel()" in self._source()

    def test_the_beat_itself_runs_off_the_event_loop(self):
        """The write is a blocking database call."""
        assert "await asyncio.to_thread(_beat)" in self._source()

    def test_a_failed_beat_does_not_kill_the_worker(self):
        import asyncio

        import pytest as _pytest

        _pytest.importorskip("arq", reason="worker-container dependency (NFR-28)")
        from app import worker

        def boom():
            raise RuntimeError("database is down")

        original = worker._beat
        worker._beat = boom
        try:
            asyncio.run(worker.heartbeat())
        finally:
            worker._beat = original


class TestScrambledPdfLosesItsSectionLabels:
    """A two-column MSDS defeats text extraction.

    pypdf reads the right column before the left, so the extracted text
    interleaves them: measured on real documents, 2 of 8 came out as msds_02,
    msds_01, msds_04, msds_03 … and section 3's chunk contained section 2's
    precautionary statements. The headers are found correctly; the body under
    each one is not the body that belongs to it. u2 would cite it as though it
    were, so no label can be trusted — a wrong citation is worse than none.
    """

    def _sections(self, settings, text):
        from app.processing.structure.msds import find_sections

        return find_sections(text, settings.msds_min_sections)

    @staticmethod
    def _doc(order):
        titles = {
            1: "화학제품과 회사에 관한 정보", 2: "유해성·위험성",
            3: "구성성분의 명칭 및 함유량", 4: "응급조치 요령",
            5: "폭발·화재시 대처방법", 6: "누출 사고시 대처방법",
            7: "취급 및 저장방법", 8: "노출방지 및 개인보호구",
            9: "물리화학적 특성", 10: "안정성 및 반응성",
            11: "독성에 관한 정보", 12: "환경에 미치는 영향",
            13: "폐기시 주의사항", 14: "운송에 필요한 정보",
            15: "법적규제 현황", 16: "그 밖의 참고사항",
        }
        return "\n\n".join(f"{n}. {titles[n]}\n본문 내용입니다." for n in order)

    def test_ascending_order_keeps_its_labels(self, settings):
        sections, status = self._sections(settings, self._doc(range(1, 17)))
        assert status.value == "structured"
        assert len(sections) == 16

    def test_interleaved_columns_are_downgraded(self, settings):
        scrambled = [2, 1, 4, 3, 6, 5, 8, 7, 11, 10, 9, 12, 15, 14, 13, 16]
        sections, status = self._sections(settings, self._doc(scrambled))
        assert status.value == "unstructured"
        assert sections == []

    def test_a_single_inversion_is_enough(self, settings):
        order = [1, 2, 4, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        _, status = self._sections(settings, self._doc(order))
        assert status.value == "unstructured"

    def test_gaps_are_still_fine(self, settings):
        """BR-18 — a missing section is not a scrambled one."""
        _, status = self._sections(settings, self._doc([1, 2, 4, 6, 7, 8, 9, 11, 13, 16]))
        assert status.value == "structured"

    def test_a_downgraded_document_is_still_indexed(self, settings, base_meta=None):
        """BR-28 — no data loss; it just carries no section codes."""
        from app.core.types import ChunkMeta
        from app.processing.chunker import chunk_document
        from app.processing.stages.structure import structure as structure_stage

        text = self._doc([2, 1, 4, 3, 6, 5, 8, 7, 11, 10, 9, 12, 15, 14, 13, 16])
        doc = structure_stage(text, DocType.MSDS, settings)
        chunks = chunk_document(text, doc, ChunkMeta(doc_type="msds",
                                                     source_url="https://e.test/x"), settings)
        assert chunks
        assert all(c.meta.section_code is None for c in chunks)


class TestUndersizedSectionsCombineWithoutClaimingOne:
    """Record-shaped sources put the chunking rule under real pressure.

    An accident record's fields are 4-15 tokens each, so one-section-one-chunk
    produced seven chunks too small for retrieval; a substance record's fields
    are 50-140 tokens and stand perfectly well alone. The rule is therefore
    about size, not document type — and a chunk that spans a boundary reports
    no section, so nothing is ever mislabelled (the guarantee from defect 1).
    """

    def _chunks(self, settings, source_id, row, doc_type):
        adapter = build_adapter(_spec(source_id), settings)
        raw = RawDocument(
            ref=SourceRef(source_id=source_id, external_id="1", url="https://e.test/1"),
            payload=adapter._project(row), media_type="application/json",
            stored_path="/tmp/r.json",
        )
        return PipelineRunner(settings).run(
            raw, doc_type, ChunkMeta(doc_type=doc_type.value, source_url=raw.ref.url)
        )

    def test_an_accident_record_becomes_one_chunk(self, settings):
        ctx = self._chunks(settings, "incident_data", INCIDENT_ROW, DocType.INCIDENT)
        assert len(ctx.chunks) == 1

    def test_that_chunk_claims_no_section(self, settings):
        ctx = self._chunks(settings, "incident_data", INCIDENT_ROW, DocType.INCIDENT)
        assert ctx.chunks[0].meta.section_code is None
        assert ctx.chunks[0].section_ordinal is None

    def test_the_whole_record_is_still_there(self, settings):
        ctx = self._chunks(settings, "incident_data", INCIDENT_ROW, DocType.INCIDENT)
        body = ctx.chunks[0].text
        for value in ("2025-12-26", "폭발", "노원구", "폐산", "광운대학교", "아세톤"):
            assert value in body

    def test_substance_routes_still_stand_alone(self, settings):
        """Sections big enough to be useful are left exactly as they were."""
        ctx = self._chunks(settings, "ncis_substance", SUBSTANCE_ROW, DocType.MSDS)
        codes = {c.meta.section_code for c in ctx.chunks}
        for expected in ("substance_inhale", "substance_skin",
                         "substance_eye", "substance_oral"):
            assert expected in codes

    def test_offsets_survive_the_merge(self, settings):
        """BR-30 — merging changes the spans, so this is where it could break."""
        ctx = self._chunks(settings, "incident_data", INCIDENT_ROW, DocType.INCIDENT)
        for chunk in ctx.chunks:
            assert ctx.extracted.text[chunk.start_offset : chunk.end_offset] == chunk.text

    def test_msds_sections_never_merge(self, settings, msds_text):
        """Defect 1's guarantee: a real MSDS section is never absorbed into its
        neighbour, so `msds_11` can never contain section 12."""
        from app.core.types import ChunkMeta
        from app.processing.chunker import chunk_document
        from app.processing.stages.structure import structure as structure_stage

        doc = structure_stage(msds_text, DocType.MSDS, settings)
        chunks = chunk_document(msds_text, doc,
                                ChunkMeta(doc_type="msds", source_url="https://e.test/m"),
                                settings)
        labelled = [c for c in chunks if c.meta.section_code]
        assert len(labelled) == len(doc.sections)
