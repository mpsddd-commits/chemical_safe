"""Re-indexing from the retained original reproduces what collection produced.

`ref.extra` is how an adapter hands the indexing path facts that are not in the
document's content - the MSDS manifest's `cas_number`, a statute's `law_name`,
a record's `title`. `_raw_from_original` rebuilt `extra` from the document row
with only `title` and `law_name`, so re-indexing the 27 MSDS documents on
2026-09-13 stripped `meta.cas_number` from 414 chunks and msds-02 dropped from
Recall@5 1.0 to 0.0. BR-38's exact identifier match reads that field.

The key list is derived from `indexing_service.py` itself, so a new
`ref.extra.get("...")` added there fails here until it survives the round trip.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.types import DocType, RawDocument, SourceRef, StructureStatus
from app.services import indexing_service as indexing_module
from app.services.indexing_service import IndexingService


def _consumed_extra_keys() -> set[str]:
    """Every literal key the indexing module reads out of an `extra` attribute.

    An `extra` read that is not a literal `.get("k")` or `["k"]` (a variable
    key, `.items()`, passing the dict along) cannot be audited this way, so it
    fails the scan instead of being skipped.
    """
    tree = ast.parse(Path(indexing_module.__file__).read_text(encoding="utf-8"))
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    keys: set[str] = set()
    unauditable: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and node.attr == "extra"):
            continue
        parent = parents.get(node)
        grand = parents.get(parent)
        if (
            isinstance(parent, ast.Attribute)
            and parent.attr == "get"
            and isinstance(grand, ast.Call)
            and grand.args
            and isinstance(grand.args[0], ast.Constant)
            and isinstance(grand.args[0].value, str)
        ):
            keys.add(grand.args[0].value)
        elif (
            isinstance(parent, ast.Subscript)
            and isinstance(parent.slice, ast.Constant)
            and isinstance(parent.slice.value, str)
        ):
            keys.add(parent.slice.value)
        else:
            unauditable.append(node.lineno)
    assert not unauditable, f"`extra` read without a literal key at lines {unauditable}"
    return keys


class _Stop(Exception):
    """Ends `process` right after the document row is written."""


class _Session:
    def add(self, _obj) -> None:
        pass

    def flush(self) -> None:
        pass


def _run_process(raw: RawDocument, doc_type: DocType, original: Path) -> dict:
    """What `process` derives from a RawDocument: the chunk base meta and the row."""
    from app.db.models import Document, Source
    from app.db.repositories.documents import DocumentRepo

    captured: dict = {}

    class Runner:
        def run(self, raw, doc_type, base_meta, from_stage=None):
            captured["meta"] = base_meta.to_dict()
            return SimpleNamespace(
                extracted=SimpleNamespace(text="", extractor="stub"),
                structured=SimpleNamespace(
                    structure_status=StructureStatus.STRUCTURED, sections=[]
                ),
                chunks=[],
                stored_path=str(original),
            )

    repo = DocumentRepo(_Session())
    repo.find_by_external = lambda *_a, **_k: None

    class Documents:
        def upsert(self, **kwargs):
            captured["upsert"] = kwargs
            document: Document = repo.upsert(**kwargs)
            document.id = 1
            document.source = Source(source_id=raw.ref.source_id)
            captured["document"] = document
            raise _Stop

    service = IndexingService.__new__(IndexingService)
    service._runner = Runner()
    service._documents = Documents()
    with pytest.raises(_Stop):
        service.process(raw, doc_type, source_pk=3)
    return captured


def _roundtrip(ref: SourceRef, tmp_path: Path) -> tuple[RawDocument, dict, RawDocument, dict]:
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-1.4 stub")
    collected = RawDocument(ref=ref, content=original.read_bytes(), media_type="application/pdf")
    first = _run_process(collected, DocType.MSDS, original)

    rebuilt = IndexingService.__new__(IndexingService)._raw_from_original(first["document"])
    second = _run_process(rebuilt, DocType.MSDS, original)
    return collected, first, rebuilt, second


def _manifest_refs(settings, tmp_path: Path) -> dict[str, SourceRef]:
    """Refs exactly as the real MSDS adapter yields them from a manifest."""
    from app.adapters.sources.msds_pdf import MsdsPdfAdapter

    manifest = tmp_path / "msds_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "id": "nhchem-sulfuric-acid",
                        "url": "https://vendor.test/h2so4.pdf",
                        "title": "황산 (SULFURIC ACID) - 남해화학",
                        "cas_number": "7664-93-9",
                    },
                    {
                        "id": "autorefinishes-ps220",
                        "url": "https://vendor.test/ps220.pdf",
                        "title": "하이큐 프라서페 PS-220 PLUS (혼합물)",
                        "cas_number": None,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    adapter = MsdsPdfAdapter(
        settings,
        {"source_id": "msds_pdf", "base_url": "https://vendor.test", "manifest_path": manifest},
    )
    refs = {}
    for ref in adapter.list_targets(None):
        refs[ref.external_id] = SourceRef(
            source_id=ref.source_id,
            external_id=ref.external_id,
            url=ref.url,
            content_hash="a" * 64,
            extra=ref.extra,
        )
    return refs


class TestKeyScan:
    def test_the_scan_finds_the_keys_the_module_reads(self):
        """Guards the scan itself: an empty set would pass every round trip."""
        assert {"title", "law_name", "cas_number"} <= _consumed_extra_keys()


class TestRoundTrip:
    def test_every_consumed_key_survives(self, tmp_path):
        """A ref carrying a distinct value for every key the indexing path reads."""
        keys = _consumed_extra_keys()
        ref = SourceRef(
            source_id="any_source",
            external_id="doc-1",
            url="https://source.test/doc-1",
            content_hash="b" * 64,
            extra={key: f"value-of-{key}"[:20] for key in sorted(keys)},
        )
        collected, first, rebuilt, second = _roundtrip(ref, tmp_path)

        lost = {
            key: (collected.ref.extra.get(key), rebuilt.ref.extra.get(key))
            for key in keys
            if collected.ref.extra.get(key) != rebuilt.ref.extra.get(key)
        }
        assert not lost, f"re-index changed extra keys (collected, rebuilt): {lost}"
        assert second["meta"] == first["meta"]
        assert second["upsert"] == first["upsert"]

    def test_reindex_carries_the_manifest_cas_number(self, settings, tmp_path):
        ref = _manifest_refs(settings, tmp_path)["nhchem-sulfuric-acid"]
        _collected, first, rebuilt, second = _roundtrip(ref, tmp_path)

        assert first["meta"]["cas_number"] == "7664-93-9"
        assert rebuilt.ref.extra["cas_number"] == "7664-93-9"
        assert second["meta"]["cas_number"] == "7664-93-9"
        assert second["upsert"] == first["upsert"]

    def test_a_mixture_datasheet_still_has_no_cas_number(self, settings, tmp_path):
        """Collected without a CAS, re-indexed without one - nothing is picked
        from the substances it lists."""
        ref = _manifest_refs(settings, tmp_path)["autorefinishes-ps220"]
        _collected, first, rebuilt, second = _roundtrip(ref, tmp_path)

        assert first["meta"]["cas_number"] is None
        assert rebuilt.ref.extra.get("cas_number") is None
        assert second["meta"]["cas_number"] is None
        assert second["upsert"] == first["upsert"]
