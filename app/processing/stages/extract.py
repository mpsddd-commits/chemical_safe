"""C19 ExtractStage - turn an original into text (FR-4, FR-9).

PDF text extraction is the single largest source of quality variance in this
unit (risk R-2). Extraction failure is `permanent`: retrying the same bytes
produces the same result, so the useful outcome is a diagnosable failure with
the original retained for inspection (FQ-8=A).
"""

from __future__ import annotations

import io
import json
from typing import Any

from app.core.errors import ExtractionError
from app.core.logging import get_logger
from app.core.types import DocType, ExtractedText, RawDocument
from app.processing.law_json import render_statute

log = get_logger(__name__)

MIN_USABLE_CHARS = 40


def extract(raw: RawDocument) -> ExtractedText:
    if raw.media_type == "application/pdf":
        return _extract_pdf(raw)
    if raw.payload is not None:
        return _extract_payload(raw)
    if raw.content is not None:
        return ExtractedText(text=raw.content.decode("utf-8", errors="replace"), extractor="bytes")
    raise ExtractionError("nothing to extract", detail=raw.ref.ref_key)


def _extract_pdf(raw: RawDocument) -> ExtractedText:
    if not raw.content:
        raise ExtractionError("empty PDF content", detail=raw.ref.ref_key)
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("pypdf is not installed", detail=str(exc)) from exc

    try:
        reader = PdfReader(io.BytesIO(raw.content))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001 - malformed PDFs raise many types
        raise ExtractionError("PDF could not be parsed", detail=str(exc)) from exc

    text = "\n\n".join(p for p in pages if p.strip())
    if len(text.strip()) < MIN_USABLE_CHARS:
        # Almost certainly a scanned document. OCR is out of scope, so this is a
        # permanent failure rather than a silent empty index entry (BR-32 spirit).
        raise ExtractionError(
            "PDF produced no usable text (likely scanned image)",
            detail=f"{len(text.strip())} chars from {len(pages)} pages",
        )
    return ExtractedText(text=text, extractor="pypdf")


def _flatten(value: Any, prefix: str = "") -> list[str]:
    lines: list[str] = []
    if isinstance(value, dict):
        for key, inner in value.items():
            if str(key).startswith("_"):
                continue
            lines.extend(_flatten(inner, f"{prefix}{key}: " if not prefix else prefix))
    elif isinstance(value, list):
        for item in value:
            lines.extend(_flatten(item, prefix))
    elif value not in (None, ""):
        lines.append(f"{prefix}{value}".strip())
    return lines


def _extract_payload(raw: RawDocument) -> ExtractedText:
    """API records become readable text so the same chunker handles every corpus."""
    payload = raw.payload or {}
    # A statute carries its own 조/항/호 decomposition; flattening it generically
    # prefixed every line with "법령: " and left the whole law as one chunk with
    # no articles (found against live data).
    statute = render_statute(payload)
    if statute:
        return ExtractedText(text=statute, extractor="law-json")
    lines = _flatten(payload)
    if not lines:
        raise ExtractionError("API payload contained no readable fields",
                              detail=json.dumps(payload)[:200])
    return ExtractedText(text="\n".join(lines), extractor="json-flatten")


def doc_type_of(raw: RawDocument, declared: DocType) -> DocType:
    return declared


# ---- two-column rescue (2026-09-01) ----------------------------------------
# pypdf reads a two-column MSDS right column first, so the extracted text
# interleaves the columns and BR-20a rightly downgrades the document to
# unstructured - documents 20 and 24 sat that way for the whole of u3/u4,
# and they were the sole cause of the 황산 GHS and 톨루엔 물리화학 card gaps.
#
# The rescue is geometry: collect text fragments with their coordinates,
# split the page at its midline, read the left column top-to-bottom and then
# the right. The detector over-triggers on table-heavy pages (measured:
# autorefinishes-ps220 went from 0 to 2 header inversions under it), so this
# extractor is NEVER the first pass. The runner calls it only after the
# normal extraction failed to structure, and adopts the result only if the
# retry structures - a rescue that cannot make anything worse.

# A page is treated as two-column when both halves carry at least this many
# fragments and share at least this many text rows. Loose on purpose: a false
# positive costs nothing here because adoption is gated on structuring.
_COLUMN_MIN_FRAGMENTS = 6
_COLUMN_MIN_SHARED_ROWS = 4


def _reassemble_lines(frags: list[tuple[float, float, str]]) -> list[str]:
    """Rows by rounded y (PDF y grows upward), left-to-right within a row."""
    rows: dict[int, list[tuple[float, str]]] = {}
    for x, y, text in frags:
        rows.setdefault(round(y), []).append((x, text))
    return [
        " ".join(text for _, text in sorted(rows[y])).strip()
        for y in sorted(rows, reverse=True)
    ]


def _two_column_rebuild(page) -> str | None:
    """Column-ordered text for a two-column page, None when it is not one."""
    frags: list[tuple[float, float, str]] = []

    def visit(text, cm, tm, font_dict, font_size) -> None:  # noqa: ANN001
        if text and text.strip():
            frags.append((float(tm[4]), float(tm[5]), text))

    page.extract_text(visitor_text=visit)
    if not frags:
        return None
    mid = float(page.mediabox.width) / 2
    left = [f for f in frags if f[0] < mid]
    right = [f for f in frags if f[0] >= mid]
    if len(left) < _COLUMN_MIN_FRAGMENTS or len(right) < _COLUMN_MIN_FRAGMENTS:
        return None
    shared_rows = {round(f[1]) for f in left} & {round(f[1]) for f in right}
    if len(shared_rows) < _COLUMN_MIN_SHARED_ROWS:
        return None
    return "\n".join(_reassemble_lines(left) + _reassemble_lines(right))


def extract_pdf_columns(raw: RawDocument) -> ExtractedText | None:
    """Re-extract a PDF with column awareness; None when no page needed it.

    Single-column pages keep pypdf's own output byte-for-byte, so a document
    that was fine yesterday cannot change under this extractor - only pages
    the detector flags are rebuilt.
    """
    if raw.media_type != "application/pdf" or not raw.content:
        return None
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw.content))
    pages: list[str] = []
    rebuilt = 0
    for page in reader.pages:
        rescue = _two_column_rebuild(page)
        if rescue is None:
            pages.append(page.extract_text() or "")
        else:
            pages.append(rescue)
            rebuilt += 1
    if rebuilt == 0:
        return None
    text = "\n\n".join(p for p in pages if p.strip())
    if len(text.strip()) < MIN_USABLE_CHARS:
        return None
    log.info("pdf_two_column_rebuild", extra={"pages_rebuilt": rebuilt, "pages": len(pages)})
    return ExtractedText(text=text, extractor="pypdf-columns")
