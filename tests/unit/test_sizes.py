"""B8 - a size rejection has to say what is too big, and by how much.

The old reason printed the limit with `:.0f` MB, so any limit under 1MB read
"한도 0MB", and a small file read "0.0MB". These pin the formatter every size
message now goes through, and the three places that use it.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

from app.auth.types import AuthenticatedUser, UploadCandidate
from app.core.errors import ValidationError
from app.core.sizes import format_size, format_sizes
from app.uploads.validator import UploadValidator

KB = 1024
MB = 1024 * 1024


def _pdf() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _candidate(data: bytes) -> UploadCandidate:
    return UploadCandidate(filename="doc.pdf", content_type="application/pdf", data=data)


def _numbers(text: str) -> list[str]:
    return re.findall(r"[\d.,]+(?:MB|KB|GB|바이트)", text)


class TestFormatter:
    def test_operating_limit_reads_as_whole_megabytes(self):
        assert format_sizes(25 * MB, 20 * MB) == ("25MB", "20MB")

    def test_operating_quota(self):
        assert format_sizes(150 * MB, 200 * MB) == ("150MB", "200MB")

    def test_a_fraction_over_is_visible(self):
        assert format_sizes(20 * MB + MB // 2, 20 * MB) == ("20.5MB", "20MB")

    def test_a_limit_under_one_megabyte_is_not_zero(self):
        actual, limit = format_sizes(600 * KB, 500 * KB)
        assert (actual, limit) == ("600KB", "500KB")

    def test_bytes_are_bytes(self):
        assert format_sizes(512, 100) == ("512바이트", "100바이트")

    def test_rounding_never_makes_a_bigger_file_equal_to_its_limit(self):
        """One byte over 1MB. "1MB (한도 1MB)" would read like a false rejection."""
        actual, limit = format_sizes(MB + 1, MB)
        assert actual != limit
        assert (actual, limit) == ("1,048,577바이트", "1,048,576바이트")

    def test_more_decimals_before_exact_bytes(self):
        actual, limit = format_sizes(20 * MB + KB, 20 * MB)
        assert (actual, limit) == ("20.001MB", "20MB")

    def test_a_non_empty_size_never_reads_as_zero(self):
        used, limit = format_sizes(40 * KB, 200 * MB)
        assert used == "0.04MB"
        assert limit == "200MB"

    def test_equal_sizes_read_equal(self):
        assert format_sizes(MB, MB) == ("1MB", "1MB")

    @pytest.mark.parametrize("limit", [1, 100, KB - 1, KB, KB + 1, MB - 1, MB, 20 * MB, 200 * MB])
    @pytest.mark.parametrize("delta", [1, 2, 7, 100, KB, MB // 3])
    def test_honest_for_every_neighbour(self, limit, delta):
        actual, shown_limit = format_sizes(limit + delta, limit)
        assert actual != shown_limit
        assert not actual.startswith("0MB") and not actual.startswith("0KB")
        assert not shown_limit.startswith("0MB") and not shown_limit.startswith("0KB")

    def test_single_size(self):
        assert format_size(0) == "0바이트"
        assert format_size(3 * MB) == "3MB"

    def test_negative_is_a_bug(self):
        with pytest.raises(ValueError):
            format_sizes(-1, 10)


class TestUploadReason:
    def test_boundary_exactly_at_the_limit_is_accepted(self, settings):
        data = _pdf()
        at = UploadValidator(settings.model_copy(update={"upload_max_bytes": len(data)}))
        assert at.validate(_candidate(data)).accepted

    def test_under_the_limit_is_accepted(self, settings):
        data = _pdf()
        roomy = UploadValidator(settings.model_copy(update={"upload_max_bytes": len(data) + 1}))
        assert roomy.validate(_candidate(data)).accepted

    def test_one_byte_over_says_so(self, settings):
        data = _pdf()
        tight = UploadValidator(settings.model_copy(update={"upload_max_bytes": len(data) - 1}))
        verdict = tight.validate(_candidate(data))
        assert not verdict.accepted
        actual, limit = _numbers(verdict.reason)
        assert actual != limit
        assert verdict.reason == f"파일 크기 {len(data):,}바이트 (한도 {len(data) - 1:,}바이트)"

    def test_a_sub_megabyte_limit_is_readable(self, settings):
        small = UploadValidator(settings.model_copy(update={"upload_max_bytes": 500 * KB}))
        verdict = small.validate(_candidate(b"%PDF-" + b"x" * (600 * KB - 5)))
        assert verdict.reason == "파일 크기 600KB (한도 500KB)"
        assert "0MB" not in verdict.reason

    def test_operating_limit(self, settings):
        validator = UploadValidator(settings)
        verdict = validator.validate(_candidate(b"%PDF-" + b"x" * (25 * MB - 5)))
        assert verdict.reason == "파일 크기 25MB (한도 20MB)"


class _Users:
    def __init__(self, used_bytes: int) -> None:
        self._used = used_bytes

    def upload_usage(self, user_id: int) -> tuple[int, int]:
        return self._used, 0


class TestQuotaReason:
    def _service(self, settings, used: int, quota: int):
        from app.services.document_service import DocumentService

        service = object.__new__(DocumentService)
        service._settings = settings.model_copy(update={"upload_quota_bytes": quota})
        service._users = _Users(used)
        return service

    def _user(self) -> AuthenticatedUser:
        return AuthenticatedUser(id=1, email="a@example.com")

    def test_operating_quota_message(self, settings):
        service = self._service(settings, used=190 * MB, quota=200 * MB)
        with pytest.raises(ValidationError) as caught:
            service._check_quota(self._user(), 20 * MB)
        assert "(사용 190MB / 한도 200MB)" in str(caught.value)

    def test_a_small_quota_is_not_zero(self, settings):
        service = self._service(settings, used=300 * KB, quota=512 * KB)
        with pytest.raises(ValidationError) as caught:
            service._check_quota(self._user(), 300 * KB)
        assert "(사용 300KB / 한도 512KB)" in str(caught.value)


class TestOneFormatter:
    def test_documents_screen_uses_the_shared_filter(self):
        """Read as text: the host test environment has no jinja2 to import the router."""
        app = Path(__file__).resolve().parents[2] / "app"
        router = (app / "web" / "routers" / "documents.py").read_text(encoding="utf-8")
        assert 'templates.env.filters["filesize"] = format_size' in router
        html = (app / "web" / "templates" / "documents.html").read_text(encoding="utf-8")
        assert "doc.size_bytes|filesize" in html
        assert "upload_max_bytes|filesize" in html
        assert "1048576" not in html
        assert "20MB" not in html

    def test_no_hand_rolled_megabytes_left_in_app(self):
        root = Path(__file__).resolve().parents[2] / "app"
        offenders = [
            str(path.relative_to(root))
            for path in root.rglob("*.py")
            if path.name != "sizes.py"
            and re.search(r"/\s*\(1024 \* 1024\)|MB\}", path.read_text(encoding="utf-8"))
        ]
        assert offenders == []
