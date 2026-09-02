"""Value objects for u5. Alive for one request, never persisted."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.types import Scope


@dataclass(frozen=True)
class AuthenticatedUser:
    """Who the request is, restored from the token (C52).

    `scope` is a property rather than something callers assemble because the
    only way owner isolation fails is by not building a `Scope`, or building the
    wrong one. Writing `Scope(owner_id=user.id)` at each call site is one place
    per site to get it wrong; asking the user object for its own scope is one
    place in total.
    """

    id: int
    email: str

    @property
    def scope(self) -> Scope:
        return Scope(owner_id=self.id)


@dataclass(frozen=True)
class UploadCandidate:
    filename: str
    content_type: str
    data: bytes

    @property
    def size_bytes(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class UploadVerdict:
    """C53's answer. `reason` is shown to the user verbatim.

    "Upload failed" tells someone nothing they can act on; "340 pages, limit
    200" tells them what to change.
    """

    accepted: bool
    page_count: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class StoredUpload:
    uuid: str
    path: str
    size_bytes: int
