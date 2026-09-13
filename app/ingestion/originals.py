"""D9 - refuse to collect where the originals cannot be kept.

`PipelineRunner._store_original` tolerates a failed write for one document, and
that stays: a single transient error must not cost the whole run. But the same
warning also swallowed a *systematic* condition. On 2026-09-07 `ingest` ran in
the `app` container, where `originals` is mounted `:ro`; every write failed,
the job reported "성공 27 / 실패 0", and all 27 MSDS documents were left without
`original_path`, which `reindex_document` refuses. Re-indexing as a way to
rebuild the corpus broke without a single error.

The check runs once per ingestion job, before anything is fetched. It writes and
removes a real file: permission bits say nothing about a read-only mount, so
asking the filesystem is the only honest test.

Re-indexing only reads originals and must not call this.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.core.errors import OriginalsNotWritableError


def ensure_originals_writable(root: Path | str) -> None:
    root = Path(root)
    try:
        if not root.is_dir():
            root.mkdir(parents=True, exist_ok=True)
        fd, probe = tempfile.mkstemp(prefix=".write-probe-", dir=root)
        os.close(fd)
        os.remove(probe)
    except OSError as exc:
        raise OriginalsNotWritableError(
            f"원본 저장 경로에 쓸 수 없어 수집을 거부합니다: {root} ({exc.strerror or exc}). "
            "원본이 남지 않으면 재색인이 불가능해집니다. "
            "수집은 worker 컨테이너에서 실행하십시오: "
            "docker compose exec worker python -m app.cli ingest --source <소스>",
            detail=str(root),
        ) from exc
