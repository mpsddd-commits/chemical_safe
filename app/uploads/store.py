"""C54 UploadStore - NFR-13, BR-141.

Outside the web root, under a generated name.

`/data/uploads/{owner_id}/{uuid}.pdf`. The original filename never appears in a
path - only in `document.upload_filename` - because a path built from user input
is a path-traversal and an overwrite waiting to happen.

The per-owner directory is not required by NFR-13. It is there so that an
isolation bug is **visible at the file system level**: `ls /data/uploads` is an
audit. A single flat directory would hide the same bug behind a database query.

Separate from `/data/originals` (BR-44) on purpose: collected originals and user
files have different backup, deletion and permission policies, and one tree
cannot express two.
"""

from __future__ import annotations

import uuid as _uuid
from pathlib import Path

from app.auth.types import StoredUpload
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

DIR_MODE = 0o700
FILE_MODE = 0o600


class UploadStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._root = Path((settings or get_settings()).uploads_dir)

    def save(self, owner_id: int, data: bytes) -> StoredUpload:
        directory = self._root / str(owner_id)
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(DIR_MODE)

        identifier = _uuid.uuid4().hex
        path = directory / f"{identifier}.pdf"
        path.write_bytes(data)
        path.chmod(FILE_MODE)
        return StoredUpload(uuid=identifier, path=str(path), size_bytes=len(data))

    @staticmethod
    def delete(path: str | None) -> None:
        """Missing is success.

        Deletion cannot be undone, so a half-deleted state must not be able to
        block the retry that finishes it. If the file is already gone, the caller
        has got what it asked for.
        """
        if not path:
            return
        try:
            Path(path).unlink(missing_ok=True)
        except OSError as exc:  # noqa: BLE001 - a stuck file must not block the row
            log.warning("upload_file_delete_failed", extra={"error": str(exc)})
