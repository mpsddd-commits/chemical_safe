"""C23 PipelineRunner - the stage chain and its resume points (DD-3, BR-44).

Stages are explicit objects rather than steps inside one method because the
boundary between them *is* the resume point. When a document fails at `embed`,
re-running it should not re-download the PDF; recording `last_stage` is what
makes that possible.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.errors import MissingRequiredMetadataError
from app.core.logging import get_logger
from app.core.types import (
    Chunk,
    ChunkMeta,
    DocType,
    ExtractedText,
    PipelineStage,
    RawDocument,
    StructuredDoc,
    StructureStatus,
)
from app.processing.chunker import chunk_document
from app.processing.injection_scan import scan
from app.processing.stages import extract as extract_stage
from app.processing.stages import structure as structure_stage
from app.processing.stages.normalize import normalize
from app.processing.structure import law as law_structure

log = get_logger(__name__)


@dataclass
class PipelineContext:
    raw: RawDocument
    doc_type: DocType
    stored_path: str | None = None
    extracted: ExtractedText | None = None
    structured: StructuredDoc | None = None
    chunks: list[Chunk] = field(default_factory=list)
    clause_numbers: dict[int, list[str]] = field(default_factory=dict)
    last_stage: PipelineStage | None = None


class PipelineRunner:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def run(
        self,
        raw: RawDocument,
        doc_type: DocType,
        base_meta: ChunkMeta,
        *,
        from_stage: PipelineStage | None = None,
    ) -> PipelineContext:
        # Carry the retained original forward even when the run resumes past
        # `fetch`. Leaving it unset wiped `document.original_path` on re-index,
        # which then made the *next* re-index impossible ("no retained
        # original") - the resume path destroying the thing resume depends on.
        ctx = PipelineContext(raw=raw, doc_type=doc_type, stored_path=raw.stored_path)
        stages: list[tuple[PipelineStage, callable]] = [
            (PipelineStage.FETCH, self._stage_fetch),
            (PipelineStage.EXTRACT, self._stage_extract),
            (PipelineStage.NORMALIZE, self._stage_normalize),
            (PipelineStage.STRUCTURE, self._stage_structure),
            (PipelineStage.CHUNK, lambda c: self._stage_chunk(c, base_meta)),
        ]

        order = [s for s, _ in stages]
        skip_until = order.index(from_stage) if from_stage in order else 0

        for index, (stage, fn) in enumerate(stages):
            if index < skip_until:
                continue
            started = time.perf_counter()
            fn(ctx)
            ctx.last_stage = stage
            # BR-58 - every stage reports its duration.
            log.info(
                "pipeline_stage_done",
                extra={
                    "stage": stage.value,
                    "ref_key": raw.ref.ref_key,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
        return ctx

    # ---- stages ----
    def _stage_fetch(self, ctx: PipelineContext) -> None:
        """C18 - the original is retained so a parsing rule change can be applied
        without going back to the source (FQ-8=A)."""
        if ctx.raw.stored_path:
            ctx.stored_path = ctx.raw.stored_path
            return
        ctx.stored_path = self._store_original(ctx.raw)

    def _stage_extract(self, ctx: PipelineContext) -> None:
        ctx.extracted = extract_stage.extract(ctx.raw)

    def _stage_normalize(self, ctx: PipelineContext) -> None:
        assert ctx.extracted is not None
        ctx.extracted = ExtractedText(
            text=normalize(ctx.extracted.text), extractor=ctx.extracted.extractor
        )

    def _stage_structure(self, ctx: PipelineContext) -> None:
        assert ctx.extracted is not None
        ctx.structured = structure_stage.structure(
            ctx.extracted.text, ctx.doc_type, self._settings
        )
        self._retry_two_column(ctx)
        if ctx.doc_type is DocType.LAW:
            # BR-22 - paragraph numbers ride along as metadata on the article.
            for section in ctx.structured.sections:
                body = ctx.extracted.text[section.start_offset : section.end_offset]
                ctx.clause_numbers[section.ordinal] = law_structure.clause_numbers(body)

    def _retry_two_column(self, ctx: PipelineContext) -> None:
        """BR-20a's other half - rescue what the guard correctly refused.

        A two-column PDF interleaves its columns under naive extraction; the
        inversion guard downgrades it to unstructured, which is right (wrong
        labels are worse than none) and lossy (documents 20 and 24 spent three
        units unstructured, costing the 황산 GHS and 톨루엔 물리화학 card
        entries). The retry re-extracts with column geometry and is adopted
        **only if the result structures** - measured on all 12 MSDS PDFs: the
        two broken documents go 16 sections/0 inversions, the ten healthy ones
        never reach this code because their first pass already structured.

        Failure here changes nothing: the unstructured-but-indexed outcome of
        BR-28 stands, exactly as before this retry existed.
        """
        assert ctx.extracted is not None and ctx.structured is not None
        if ctx.structured.structure_status is not StructureStatus.UNSTRUCTURED:
            return
        if ctx.doc_type not in (DocType.MSDS, DocType.USER_UPLOAD):
            return
        try:
            retry = extract_stage.extract_pdf_columns(ctx.raw)
        except Exception as exc:  # noqa: BLE001 - a rescue must never break the run
            log.warning("pdf_column_retry_failed", extra={"error": str(exc)})
            return
        if retry is None:
            return
        text = normalize(retry.text)
        candidate = structure_stage.structure(text, ctx.doc_type, self._settings)
        if candidate.structure_status is not StructureStatus.STRUCTURED:
            log.info(
                "pdf_column_retry_not_adopted",
                extra={"ref_key": ctx.raw.ref.ref_key, "status": candidate.structure_status.value},
            )
            return
        log.info(
            "pdf_column_retry_adopted",
            extra={"ref_key": ctx.raw.ref.ref_key, "sections": len(candidate.sections)},
        )
        ctx.extracted = ExtractedText(text=text, extractor=retry.extractor)
        ctx.structured = candidate

    def _stage_chunk(self, ctx: PipelineContext, base_meta: ChunkMeta) -> None:
        assert ctx.extracted is not None and ctx.structured is not None
        # BR-32 - refuse before doing any more work.
        if not base_meta.source_url or not base_meta.doc_type:
            raise MissingRequiredMetadataError(
                "source_url and doc_type are required to index a document",
                detail=ctx.raw.ref.ref_key,
            )
        ctx.chunks = chunk_document(
            ctx.extracted.text,
            ctx.structured,
            base_meta,
            self._settings,
            ctx.clause_numbers,
        )
        self._flag_suspected_injection(ctx)

    def _flag_suspected_injection(self, ctx: PipelineContext) -> None:
        """N3 / SP-4 - scan once at index time, not on every query.

        The flag reaches the prompt as an attribute (SP-5). It never removes a
        chunk: MSDS first-aid text is imperative by nature, so excluding on
        suspicion would delete legitimate safety information.
        """
        if not self._settings.injection_scan_enabled:
            return
        flagged = 0
        for chunk in ctx.chunks:
            result = scan(chunk.text)
            # `chunk.meta` is JSONB, so this needs no migration.
            chunk.meta.suspected_injection = result.suspected
            chunk.meta.injection_signals = result.reasons
            if result.suspected:
                flagged += 1
        if flagged:
            log.info(
                "injection_signals_flagged",
                extra={"ref_key": ctx.raw.ref.ref_key, "chunks": flagged},
            )

    # ---- helpers ----
    @staticmethod
    def _suffix_for(media_type: str) -> str:
        """The stored file must describe what it actually is.

        Writing every byte payload as `.pdf` broke re-indexing: the extension is
        what `_raw_from_original` reads back, so a text document came back
        labelled as a PDF and failed extraction permanently (found in Build &
        Test). `document.original_media_type` is the authoritative record, and
        the extension is kept consistent with it.
        """
        return {
            "application/pdf": ".pdf",
            "application/json": ".json",
            "application/xml": ".xml",
            "text/xml": ".xml",
            "text/html": ".html",
            "text/plain": ".txt",
        }.get(media_type, ".bin")

    def _store_original(self, raw: RawDocument) -> str | None:
        root = Path(self._settings.originals_dir) / raw.ref.source_id
        safe_name = raw.ref.external_id.replace("/", "_").replace("\\", "_")[:180]
        try:
            root.mkdir(parents=True, exist_ok=True)
            if raw.content is not None:
                path = root / f"{safe_name}{self._suffix_for(raw.media_type)}"
                path.write_bytes(raw.content)
            elif raw.payload is not None:
                import json

                path = root / f"{safe_name}.json"
                path.write_text(
                    json.dumps(raw.payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            else:
                return None
            return str(path)
        except OSError as exc:
            # Retaining the original is valuable but not worth failing the whole
            # document over; the source URL is still recorded (BR-32).
            log.warning(
                "original_not_stored",
                extra={"ref_key": raw.ref.ref_key, "error": str(exc)},
            )
            return None
