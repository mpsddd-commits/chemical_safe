"""P9 - document management (FR-27, FR-29, FR-46) and P10 - history (FR-32, FR-47).

Both screens require an account. `require_user` raises rather than returning
`None`, and the handler below turns that into a redirect - so a new screen added
to this router is protected by default rather than by remembering.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.types import AuthenticatedUser, UploadCandidate
from app.core.errors import PermissionDeniedError, ValidationError
from app.core.logging import get_logger
from app.jobs.queue import TaskQueue
from app.services.account_service import AccountService
from app.services.document_service import DocumentService
from app.web.deps import (
    get_session,
    issue_csrf,
    require_user,
    set_csrf_cookie,
    verify_csrf,
)

log = get_logger(__name__)
router = APIRouter(tags=["documents"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def _render(request: Request, template: str, **context) -> HTMLResponse:
    token = issue_csrf(request)
    status_code = context.pop("status_code", 200)
    response = templates.TemplateResponse(
        request, template, {"csrf_token": token, **context}, status_code=status_code
    )
    set_csrf_cookie(response, token)
    return response


@router.get("/documents", response_class=HTMLResponse)
def documents_page(
    request: Request,
    user: AuthenticatedUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    service = DocumentService(session)
    return _render(
        request,
        "documents.html",
        active="documents",
        user=user,
        documents=service.list_documents(user),
        error=request.query_params.get("error"),
    )


@router.post("/documents")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    csrf_token: str = Form(""),
    user: AuthenticatedUser = Depends(require_user),
    session: Session = Depends(get_session),
):
    verify_csrf(request, csrf_token)
    data = await file.read()
    candidate = UploadCandidate(
        filename=file.filename or "upload.pdf",
        content_type=file.content_type or "",
        data=data,
    )
    try:
        document_id = DocumentService(session).upload(user, candidate)
    except ValidationError as exc:
        # The reason is shown verbatim: "upload failed" gives the person nothing
        # to act on, "340 pages, limit 200" tells them what to change.
        return _render(
            request,
            "documents.html",
            active="documents",
            user=user,
            documents=DocumentService(session).list_documents(user),
            error=str(exc),
            status_code=400,
        )

    # BR-143 - the request stops here. A 200-page PDF parsed inside an HTTP
    # request is a timeout, and the user learns nothing about what happened.
    # The job row is what makes the outcome - including a failure - visible.
    job_id = DocumentService(session).create_index_job(user, document_id)
    await TaskQueue().enqueue_and_close(
        "run_index_upload", document_id=document_id, job_id=job_id
    )
    return RedirectResponse("/documents", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/documents/{document_id}/delete")
def delete_document(
    request: Request,
    document_id: int,
    csrf_token: str = Form(""),
    user: AuthenticatedUser = Depends(require_user),
    session: Session = Depends(get_session),
):
    verify_csrf(request, csrf_token)
    try:
        DocumentService(session).delete(user, document_id)
    except PermissionDeniedError as exc:
        # 404, not 403 (BR-146). A 403 would confirm the document exists, and
        # ids are sequential.
        raise HTTPException(status_code=404, detail="document not found") from exc
    return RedirectResponse("/documents", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/documents/{document_id}/reindex")
async def reindex_document(
    request: Request,
    document_id: int,
    csrf_token: str = Form(""),
    user: AuthenticatedUser = Depends(require_user),
    session: Session = Depends(get_session),
):
    verify_csrf(request, csrf_token)
    try:
        DocumentService(session).owned(user, document_id)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc
    job_id = DocumentService(session).create_index_job(user, document_id)
    await TaskQueue().enqueue_and_close(
        "run_index_upload", document_id=document_id, job_id=job_id
    )
    return RedirectResponse("/documents", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/documents/{document_uuid}/file")
def download_document(
    document_uuid: str,
    user: AuthenticatedUser = Depends(require_user),
    session: Session = Depends(get_session),
):
    """The `source_url` a citation points at, resolved for its owner only.

    Uploaded documents have no public URL, so `document.source_url` is this
    route. It satisfies BR-105 ("every value has somewhere to check it") for the
    person who uploaded it, and is a 404 for everyone else.
    """
    from sqlalchemy import select

    from app.db.models import Document

    document = session.scalar(
        select(Document).where(Document.external_id == document_uuid)
    )
    if document is None or document.owner_id != user.id or not document.original_path:
        log.info(
            "isolation_denied",
            extra={"document_uuid": document_uuid, "user_id": user.id},
        )
        raise HTTPException(status_code=404, detail="document not found")
    return FileResponse(
        document.original_path,
        media_type="application/pdf",
        filename=document.upload_filename or "document.pdf",
    )


@router.get("/history", response_class=HTMLResponse)
def history_page(
    request: Request,
    user: AuthenticatedUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """P10. Only this user's questions (BR-149), re-read from what u2 stored.

    Anonymous queries carry `owner_id IS NULL` and belong to nobody, so they are
    not here - the cost of keeping public queries open (BR-151).
    """
    return _render(
        request,
        "history.html",
        active="history",
        user=user,
        entries=AccountService(session).query_history(user),
    )
