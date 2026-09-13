"""Backlog D9 - collecting where the originals cannot be kept is refused up front.

2026-09-07: `ingest` ran in the `app` container (`originals` mounted `:ro`). Every
original failed to store with a warning, the job said "성공 27 / 실패 0", and all
27 MSDS documents lost `original_path`, so re-indexing could no longer rebuild
them. The per-document tolerance was right; letting a systematic condition pass
through it was not.
"""

from __future__ import annotations

import errno
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.errors import FailureKind, OriginalsNotWritableError
from app.core.types import (
    ChunkMeta,
    DocType,
    JobKind,
    JobStatus,
    PipelineStage,
    RawDocument,
    SourceRef,
)
from app.ingestion import originals as originals_mod
from app.ingestion.originals import ensure_originals_writable
from app.jobs.tracker import JobTracker
from app.processing.runner import PipelineRunner
from app.services import ingestion_service as ingestion_mod
from tests.unit.test_job_tracker import FakeJobRepo


def _unwritable_root(tmp_path: Path) -> Path:
    """A real path the filesystem refuses: its parent is a regular file."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    return blocker / "originals"


def _read_only_mount(monkeypatch) -> None:
    """An existing directory that refuses writes, as a `:ro` mount does."""

    def refuse(*_args, **_kwargs):
        raise OSError(errno.EROFS, "Read-only file system")

    monkeypatch.setattr(originals_mod.tempfile, "mkstemp", refuse)


def _service(settings, root: Path):
    service = ingestion_mod.IngestionService.__new__(ingestion_mod.IngestionService)
    service._settings = settings.model_copy(update={"originals_dir": root})
    repo = FakeJobRepo()
    service._tracker = JobTracker(repo)
    job_id = service._tracker.create(JobKind.INGEST, {"source_id": "msds_pdf"})
    return service, repo, job_id


def _forbid_collecting(monkeypatch) -> list[str]:
    touched: list[str] = []

    def load_specs():
        touched.append("load_source_specs")
        return []

    def build(*_args, **_kwargs):
        touched.append("build_adapter")
        raise AssertionError("an adapter was built for a refused job")

    monkeypatch.setattr(ingestion_mod, "load_source_specs", load_specs)
    monkeypatch.setattr(ingestion_mod, "build_adapter", build)
    return touched


class TestProbe:
    def test_writable_root_passes_and_leaves_nothing_behind(self, tmp_path):
        ensure_originals_writable(tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_missing_root_is_created(self, tmp_path):
        root = tmp_path / "originals"
        ensure_originals_writable(root)
        assert root.is_dir()

    def test_unwritable_root_raises_a_permanent_error_naming_the_fix(self, tmp_path):
        root = _unwritable_root(tmp_path)
        with pytest.raises(OriginalsNotWritableError) as info:
            ensure_originals_writable(root)
        assert info.value.kind is FailureKind.PERMANENT
        assert str(root) in str(info.value)
        assert "수집은 worker 컨테이너에서 실행하십시오" in str(info.value)

    def test_read_only_existing_directory_is_caught(self, tmp_path, monkeypatch):
        _read_only_mount(monkeypatch)
        with pytest.raises(OriginalsNotWritableError):
            ensure_originals_writable(tmp_path)


class TestIngestRefusal:
    def test_a_read_only_root_is_refused_before_anything_is_collected(
        self, settings, tmp_path, monkeypatch
    ):
        """(a) The job ends failed and nothing downstream of the guard ran."""
        _read_only_mount(monkeypatch)
        touched = _forbid_collecting(monkeypatch)
        service, repo, job_id = _service(settings, tmp_path)

        outcome = service.execute(job_id, "msds_pdf")

        assert touched == []
        assert outcome["refused"] is True
        assert outcome["status"] == JobStatus.FAILED.value
        assert "worker" in outcome["error"]
        (item,) = repo.jobs[job_id].items
        assert item.ref_key == "msds_pdf:__originals__"
        assert item.failure_kind == FailureKind.PERMANENT.value

    def test_an_unwritable_path_is_refused_too(self, settings, tmp_path, monkeypatch):
        touched = _forbid_collecting(monkeypatch)
        service, _repo, job_id = _service(settings, _unwritable_root(tmp_path))

        outcome = service.execute(job_id, "msds_pdf")

        assert touched == []
        assert outcome["status"] == JobStatus.FAILED.value

    def test_a_writable_root_goes_on_to_collect(self, settings, tmp_path, monkeypatch):
        """(b) Past the guard, the run reaches the source configuration."""
        touched = _forbid_collecting(monkeypatch)
        service, _repo, job_id = _service(settings, tmp_path)

        # The stubbed catalogue is empty, so the run stops at the next step -
        # which is the point: it got there.
        with pytest.raises(Exception, match="not declared in config"):
            service.execute(job_id, "msds_pdf")

        assert touched == ["load_source_specs"]
        assert list(tmp_path.iterdir()) == []


class TestPerDocumentToleranceStays:
    def test_one_original_failing_to_store_is_still_only_a_warning(self, settings, tmp_path):
        """(c) The document is indexed without an original; the run is not stopped."""
        relocated = settings.model_copy(update={"originals_dir": _unwritable_root(tmp_path)})
        ref = SourceRef(source_id="src", external_id="doc-1", url="https://example.test/doc")
        raw = RawDocument(
            ref=ref,
            payload={"title": "시험 문서", "body": "본문 내용입니다."},
            media_type="application/json",
        )
        meta = ChunkMeta(doc_type="msds", source_url="https://example.test/doc")

        ctx = PipelineRunner(relocated).run(raw, DocType.MSDS, meta)

        assert ctx.stored_path is None
        assert ctx.chunks


class TestReindexIsNotGuarded:
    def test_reindex_reads_originals_from_a_read_only_root(
        self, settings, tmp_path, monkeypatch
    ):
        """(d) Re-indexing only reads, so the `app` container may run it."""
        from app.services.indexing_service import IndexingService

        original = tmp_path / "doc-1.json"
        original.write_text(
            json.dumps({"title": "시험 문서", "body": "본문 내용입니다."}), encoding="utf-8"
        )
        _read_only_mount(monkeypatch)

        service = IndexingService.__new__(IndexingService)
        service._settings = settings.model_copy(update={"originals_dir": tmp_path})
        document = SimpleNamespace(
            id=1, doc_type="msds", source_id=None, source=None, owner_id=None,
            external_id="doc-1", source_url="https://example.test/doc",
            published_at=None, revised_at=None, content_hash=None, title="시험 문서",
            law_name=None, original_path=str(original),
            original_media_type="application/json",
        )
        service._documents = SimpleNamespace(get=lambda _id: document)
        runs = []

        def process(raw, doc_type, *, source_pk, from_stage, owner_id):
            meta = ChunkMeta(doc_type=doc_type.value, source_url=raw.ref.url)
            ctx = PipelineRunner(service._settings).run(
                raw, doc_type, meta, from_stage=from_stage
            )
            runs.append((from_stage, ctx.stored_path, len(ctx.chunks)))
            return ctx

        service.process = process

        service.reindex_document(1)

        assert runs == [(PipelineStage.EXTRACT, str(original), runs[0][2])]
        assert runs[0][2] > 0
