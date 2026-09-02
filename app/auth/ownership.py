"""C55 OwnershipFilter - FR-28, NFR-15, BR-145·BR-146.

**The only place in the application that constructs a `Scope`.**

That is the whole design. u1 made `Scope` a required argument on every search
method (DD-19) precisely so isolation could not be forgotten later; the failure
mode that leaves is building the scope wrongly, or building one somewhere that
nobody reviews. Funnelling construction through here reduces that to one
function, and `tests/unit/test_scope_discipline.py` enforces that no other
module calls `Scope(` at all.

Two exceptions exist and both are explicit: `Scope.public()` in the evaluator
(BR-148) and the tests.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth.types import AuthenticatedUser
from app.core.errors import PermissionDeniedError
from app.core.logging import get_logger
from app.core.types import Scope
from app.db.models import Document

log = get_logger(__name__)


def scope_for(user: AuthenticatedUser | None) -> Scope:
    """Anonymous callers get the public corpus; signed-in callers get theirs too.

    Anonymous is not an error (BR-151). Nothing in FR-31~33 says a question
    needs an account, and removing the public query would be a feature cut the
    requirements never asked for.
    """
    return Scope.public() if user is None else user.scope


def owned_document(
    session: Session, document_id: int, user: AuthenticatedUser
) -> Document:
    """The caller's own document, or `PermissionDeniedError`.

    Routers turn that into **404, not 403** (BR-146). A 403 confirms the
    document exists, and document ids are sequential integers - which would let
    anyone count how many files another account holds, and when they arrived.

    A document that exists but is public is also denied: the management screen
    is "what I uploaded", not "everything I can search".
    """
    document = session.get(Document, document_id)
    if document is None or document.owner_id != user.id:
        # Logged because isolation that never reports a denial cannot be
        # observed to work at all - zero denials and no logging look identical
        # from the outside (OP-1).
        log.info(
            "isolation_denied",
            extra={"document_id": document_id, "user_id": user.id},
        )
        raise PermissionDeniedError(f"document {document_id} is not available")
    return document
