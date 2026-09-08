"""Fill `document.title` for the documents collected before the adapters set it.

Measured 2026-09-08: substance 49/49, incident 12/12 and law 9/9 had no title,
so the generator received evidence blocks reading `title=""` and could not tell
which of five `substance_eye` chunks was the 암모니아 one. It refused, correctly.
`app.core.document_titles` explains the mechanism; this script repairs the rows
already in the database, and the adapters keep the next collection from undoing
the repair.

An UPDATE is enough. `document.title` is **not** copied into `chunk.meta` —
`ChunkMeta` has no title field — and `rag/citations.resolve_evidence` joins
`document` at query time, so the next query sees the new value with no
re-collection and no re-indexing. Chunk bodies do not change here.

Three rules this script keeps:

  * **It invents nothing.** Every title comes from the substance master or from
    the stored original response. A document whose source is missing keeps its
    empty title and is reported. Blank is better than fabricated.
  * **It is idempotent.** Only rows with no title are written, so a second run
    updates nothing.
  * **It says what it skipped.** Silence about a skipped row is how 70 anonymous
    documents went unnoticed for a week.

Run it from the host (the container has no `scripts/`):

    set -a; . ./.env; set +a
    PYTHONIOENCODING=utf-8 POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 \
        python scripts/backfill_document_titles.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.core.document_titles import (  # noqa: E402
    incident_title,
    law_title,
    substance_title,
)
from app.core.types import DocType  # noqa: E402
from app.db.engine import init_engine, session_scope  # noqa: E402

# `sources.yaml` `source_id` -> the directory `stage_original` writes into.
_ORIGINAL_DIRS = {
    DocType.LAW: "law_api",
    DocType.INCIDENT: "incident_data",
}


def _load_original(root: Path, doc_type: DocType, external_id: str) -> dict[str, Any] | None:
    path = root / _ORIGINAL_DIRS[doc_type] / f"{external_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _substance_titles(session: Any) -> dict[int, str]:
    """Titles for `substance` documents, from the master they are linked to.

    `document_substance` is the link the indexing path already writes (BR-97), so
    this reads the same fact rather than re-deriving it from the record text.
    """
    from sqlalchemy import text as sql_text

    rows = session.execute(
        sql_text(
            """
            SELECT d.id, s.name_ko, s.name_en, s.cas_number
              FROM document d
              JOIN document_substance ds ON ds.document_id = d.id
                                        AND ds.relation = 'subject'
              JOIN substance s ON s.id = ds.substance_id
             WHERE d.doc_type = 'substance'
            """
        )
    ).all()
    titles: dict[int, str] = {}
    for document_id, name_ko, name_en, cas_number in rows:
        title = substance_title(name_ko, name_en, cas_number)
        if title:
            titles[int(document_id)] = title
    return titles


def _title_from_original(
    root: Path, doc_type: DocType, external_id: str
) -> tuple[str | None, str | None]:
    """(title, reason it is missing). Exactly one of the two is set."""
    payload = _load_original(root, doc_type, external_id)
    if payload is None:
        return None, f"원본 없음: {root / _ORIGINAL_DIRS[doc_type] / (external_id + '.json')}"

    if doc_type is DocType.LAW:
        info = (payload.get("법령") or {}).get("기본정보") or {}
        title = law_title(info.get("법령명_한글") or info.get("법령명한글"))
        return (title, None) if title else (None, "원본에 법령명_한글 없음")

    title = incident_title(
        payload.get("place"),
        payload.get("incident_type"),
        payload.get("occurred_at"),
        area=payload.get("area"),
    )
    return (title, None) if title else (None, "원본에 place/area/incident_type 모두 없음")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--originals",
        type=Path,
        default=None,
        help="collected originals root (default: ORIGINALS_DIR, else data/originals)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would change, write nothing"
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    root = args.originals
    if root is None:
        root = settings.originals_dir if settings.originals_dir.exists() else Path("data/originals")

    from sqlalchemy import text as sql_text

    init_engine(settings)
    updated = 0
    already = 0
    skipped: list[tuple[str, str, str]] = []

    with session_scope() as session:
        substance_titles = _substance_titles(session)
        rows = session.execute(
            sql_text(
                "SELECT id, doc_type, external_id, title FROM document"
                " WHERE doc_type IN ('substance', 'law', 'incident') ORDER BY doc_type, id"
            )
        ).all()

        for document_id, doc_type_value, external_id, current in rows:
            doc_type = DocType(doc_type_value)
            label = f"{doc_type_value}/{external_id}"
            if current and current.strip():
                already += 1
                continue

            if doc_type is DocType.SUBSTANCE:
                title = substance_titles.get(int(document_id))
                reason = None if title else "document_substance 에 subject 연결 없음"
            else:
                title, reason = _title_from_original(root, doc_type, str(external_id))

            if not title:
                skipped.append((label, str(document_id), reason or "알 수 없음"))
                continue

            print(f"{'[dry-run] ' if args.dry_run else ''}{label} -> {title}")
            if not args.dry_run:
                session.execute(
                    sql_text("UPDATE document SET title = :title WHERE id = :id"),
                    {"title": title, "id": document_id},
                )
            updated += 1

    verb = "채울 대상" if args.dry_run else "채움"
    print(f"\n{verb} {updated}건 · 이미 제목 있음 {already}건 · 건너뜀 {len(skipped)}건")
    for label, document_id, reason in skipped:
        print(f"  건너뜀 {label} (document {document_id}): {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
