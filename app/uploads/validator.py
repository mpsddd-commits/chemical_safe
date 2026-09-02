"""C53 UploadValidator - FR-30, BR-139·BR-140.

**This is not virus scanning and the code says so.**

What it does: refuses anything that is not structurally a PDF, that pypdf
cannot parse, that exceeds the size or page limits, or that carries an
auto-executing action or an embedded file.

What it does not do: detect known malware signatures, and stop a new pypdf
vulnerability - parsing *is* the attack surface, and this module is the thing
doing the parsing.

The real defence is structural rather than a rule in this file: **safeenv never
executes an uploaded file.** It extracts text. No rendering, no preview, no link
following, no external resource loading. An anti-virus container was considered
and rejected because it breaks `docker compose up` as a single command (NFR-29)
while adding little on top of that structure.

Order matters. The cheap checks run first so a 25MB file never reaches the
parser.
"""

from __future__ import annotations

import io

from app.auth.types import UploadCandidate, UploadVerdict
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

PDF_MAGIC = b"%PDF-"

# Objects that make a PDF do something on its own. A datasheet has no reason to
# carry any of them.
DANGEROUS_MARKERS: tuple[bytes, ...] = (
    b"/JavaScript",
    b"/JS",
    b"/Launch",
    b"/EmbeddedFile",
    b"/OpenAction",
    b"/AA",
)


class UploadValidator:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def validate(self, candidate: UploadCandidate) -> UploadVerdict:
        settings = self._settings

        # 1. Size. Bytes only - the cheapest possible check.
        if candidate.size_bytes == 0:
            return UploadVerdict(False, reason="빈 파일입니다.")
        if candidate.size_bytes > settings.upload_max_bytes:
            limit_mb = settings.upload_max_bytes / (1024 * 1024)
            actual_mb = candidate.size_bytes / (1024 * 1024)
            return UploadVerdict(
                False,
                reason=f"파일 크기 {actual_mb:.1f}MB (한도 {limit_mb:.0f}MB)",
            )

        # 2. Magic bytes. The extension and the MIME type are what the uploader
        #    claims; this is what the file is.
        if not candidate.data.startswith(PDF_MAGIC):
            return UploadVerdict(
                False, reason="PDF 파일이 아닙니다 (파일 시작 바이트 불일치)."
            )

        # 3. Parse. A file that no parser accepts cannot be indexed either.
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(candidate.data))
            page_count = len(reader.pages)
        except Exception as exc:  # noqa: BLE001 - any parse failure is a rejection
            return UploadVerdict(False, reason=f"PDF 를 읽을 수 없습니다: {exc}")

        if page_count == 0:
            return UploadVerdict(False, reason="페이지가 없는 PDF 입니다.")

        # 4. Pages.
        if page_count > settings.upload_max_pages:
            return UploadVerdict(
                False,
                reason=f"페이지 수 {page_count} (한도 {settings.upload_max_pages})",
            )

        # 5. Auto-executing content. Scanned over raw bytes rather than the
        #    object tree: object streams can hide the tree from a shallow walk,
        #    and a false positive here costs a rejection message, not safety.
        found = [m.decode() for m in DANGEROUS_MARKERS if m in candidate.data]
        if found:
            return UploadVerdict(
                False,
                page_count=page_count,
                reason=f"자동 실행 요소가 포함되어 있습니다: {', '.join(found)}",
            )

        return UploadVerdict(True, page_count=page_count)
