"""S7 DocumentService - FR-27, FR-29, FR-46.

Upload, list, delete, re-index. Every method takes the user first, because
**anonymous callers have no business here at all** - that is not a check inside
the method, it is the shape of the signature.

Indexing is not done here. The upload request validates and stores, then queues
(BR-143); the worker runs the same `IndexingService` the public corpus goes
through, with one extra argument (BR-142). An upload-only indexing path would
let chunking and structure rules drift between what a user uploads and what the
system collected, and then the same document would be cited two different ways.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.ownership import owned_document
from app.auth.types import AuthenticatedUser, UploadCandidate
from app.core.config import Settings, get_settings
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.core.types import DocType, StructureStatus
from app.db.models import Document
from app.db.repositories.accounts import UserRepo
from app.db.repositories.documents import DocumentRepo
from app.uploads.store import UploadStore
from app.uploads.validator import UploadValidator

log = get_logger(__name__)


@dataclass
class DocumentSummary:
    id: int
    # The download route is keyed on this, not on `id`: citations point at the
    # same URL and they only have the external identifier.
    uuid: str | None
    filename: str
    size_bytes: int
    page_count: int | None
    structure_status: str
    chunk_count: int
    created_at: datetime
    # From the indexing job, so a failure is visible rather than looking like
    # "still working" forever (FQ7-6).
    index_status: str | None = None
    index_error: str | None = None


class DocumentService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._s = session
        self._settings = settings or get_settings()
        self._documents = DocumentRepo(session)
        self._users = UserRepo(session)
        self._validator = UploadValidator(self._settings)
        self._store = UploadStore(self._settings)

    # ---- W21 upload ----
    def upload(self, user: AuthenticatedUser, candidate: UploadCandidate) -> int:
        # Quota before validation: there is no reason to parse 20MB for someone
        # who cannot store it either way (UP-4).
        self._check_quota(user, candidate.size_bytes)

        verdict = self._validator.validate(candidate)
        if not verdict.accepted:
            log.info("upload_rejected", extra={"user_id": user.id, "reason": verdict.reason})
            raise ValidationError(verdict.reason or "업로드할 수 없는 파일입니다.")

        # Only now does anything touch the disk. A rejected file left behind is
        # itself a store (UP-2).
        stored = self._store.save(user.id, candidate.data)

        document = Document(
            source_id=None,
            external_id=stored.uuid,
            doc_type=DocType.USER_UPLOAD.value,
            title=candidate.filename,
            # NOT NULL, and an upload has no URL. This is the app's own route:
            # the owner can actually open it, which is what BR-105 asks of a
            # source. To anyone else it is a 404, and that is the isolation.
            #
            # `/file` is part of it. Without the suffix this pointed at a route
            # that does not exist, so every citation of an uploaded document was
            # a dead link - found by following one.
            source_url=f"/documents/{stored.uuid}/file",
            original_path=stored.path,
            original_media_type="application/pdf",
            structure_status=StructureStatus.UNSTRUCTURED.value,
            owner_id=user.id,
            upload_filename=candidate.filename,
            upload_size_bytes=stored.size_bytes,
            upload_page_count=verdict.page_count,
        )
        self._s.add(document)
        self._s.flush()
        log.info(
            "upload_accepted",
            extra={
                "user_id": user.id,
                "document_id": document.id,
                "pages": verdict.page_count,
                "bytes": stored.size_bytes,
            },
        )
        return document.id

    def create_index_job(self, user: AuthenticatedUser, document_id: int) -> int:
        """A job row so the screen can say what happened (FR-6, FR-8).

        Without it an indexing failure is invisible: the document sits at zero
        chunks and the list shows "indexing" forever. Measured - a blank PDF
        raises `ExtractionError: PDF produced no usable text`, the arq job logs
        it, and the person who uploaded the file learns nothing. Scanned MSDS
        PDFs are common, so this is the ordinary case rather than an edge one.
        """
        from app.core.types import JobKind
        from app.db.repositories.jobs import JobRepo
        from app.jobs.tracker import JobTracker

        tracker = JobTracker(JobRepo(self._s))
        job_id = tracker.create(
            JobKind.UPLOAD_INDEX, {"document_id": document_id, "owner_id": user.id}
        )
        tracker.add_items(job_id, [f"upload:{document_id}"])
        return job_id

    def _check_quota(self, user: AuthenticatedUser, incoming: int) -> None:
        used_bytes, used_docs = self._users.upload_usage(user.id)
        if used_docs >= self._settings.upload_quota_documents:
            raise ValidationError(
                f"문서 수 한도에 도달했습니다 ({self._settings.upload_quota_documents}건). "
                "기존 문서를 삭제한 뒤 다시 시도하세요."
            )
        if used_bytes + incoming > self._settings.upload_quota_bytes:
            limit_mb = self._settings.upload_quota_bytes / (1024 * 1024)
            used_mb = used_bytes / (1024 * 1024)
            raise ValidationError(
                f"저장 용량 한도를 초과합니다 (사용 {used_mb:.0f}MB / 한도 {limit_mb:.0f}MB)."
            )

    # ---- W23 list / delete / reindex ----
    def list_documents(self, user: AuthenticatedUser) -> list[DocumentSummary]:
        """Only what this user uploaded.

        The public corpus is not listed here. This screen answers "what did I
        upload", not "what can I search" - conflating them would suggest the
        user can delete the 78 collected documents.
        """
        from sqlalchemy import func

        from app.db.models import ChunkRow

        rows = self._s.execute(
            select(
                Document,
                func.count(ChunkRow.id),
            )
            .outerjoin(ChunkRow, ChunkRow.document_id == Document.id)
            .where(Document.owner_id == user.id)
            .group_by(Document.id)
            .order_by(Document.created_at.desc())
        ).all()
        statuses = self._index_statuses([document.id for document, _ in rows])
        return [
            DocumentSummary(
                id=document.id,
                uuid=document.external_id,
                filename=document.upload_filename or document.title or "(이름 없음)",
                size_bytes=document.upload_size_bytes or 0,
                page_count=document.upload_page_count,
                structure_status=document.structure_status,
                chunk_count=int(chunk_count or 0),
                created_at=document.created_at,
                index_status=statuses.get(document.id, (None, None))[0],
                index_error=statuses.get(document.id, (None, None))[1],
            )
            for document, chunk_count in rows
        ]

    def _index_statuses(
        self, document_ids: list[int]
    ) -> dict[int, tuple[str | None, str | None]]:
        """Latest indexing job outcome per document, from u1's own tables."""
        from app.db.models import Job, JobItem

        if not document_ids:
            return {}
        rows = self._s.execute(
            select(Job.params, JobItem.status, JobItem.failure_reason)
            .join(JobItem, JobItem.job_id == Job.id)
            .where(Job.kind == "upload_index")
            .order_by(Job.id.desc())
        ).all()
        latest: dict[int, tuple[str | None, str | None]] = {}
        for params, status, reason in rows:
            document_id = (params or {}).get("document_id")
            if document_id in document_ids and document_id not in latest:
                latest[document_id] = (status, reason)
        return latest

    def delete(self, user: AuthenticatedUser, document_id: int) -> None:
        """Hard delete (BR-144).

        Database first, file second. The other order leaves a row pointing at a
        file that is gone if the transaction then fails; this one leaves an
        orphan file, which is the cheaper of the two wrongs and is visible in
        `/data/uploads`.
        """
        document = owned_document(self._s, document_id, user)
        path = document.original_path
        self._documents.delete(document_id)
        self._store.delete(path)
        log.info("document_deleted", extra={"user_id": user.id, "document_id": document_id})

    def owned(self, user: AuthenticatedUser, document_id: int) -> Document:
        return owned_document(self._s, document_id, user)
