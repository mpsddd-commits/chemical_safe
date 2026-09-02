"""Exception hierarchy and FailureKind classification (BR-42, BR-43)."""

from __future__ import annotations

from enum import StrEnum


class FailureKind(StrEnum):
    """Three-way error classification (FQ-11=A).

    `POLICY_BLOCKED` is deliberately separate from `PERMANENT`: it must never be
    retried *and* must never be re-attempted on a later run until the policy
    check itself flips to allowed (BR-43). A two-way split cannot express that.
    """

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    POLICY_BLOCKED = "policy_blocked"


class SafeenvError(Exception):
    """Base for all application errors."""

    kind: FailureKind = FailureKind.PERMANENT

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


# ---- Transient (retryable, BR-41) ----
class TransientError(SafeenvError):
    kind = FailureKind.TRANSIENT


class SourceUnavailableError(TransientError):
    """Network failure, timeout, HTTP 5xx or 429."""


class EmbeddingUnavailableError(TransientError):
    """Model download or inference failed in a way that may recover."""


class QuotaExhaustedError(TransientError):
    """The provider's quota is spent - a wait, not a fault (u2).

    Still `TRANSIENT`, because it does recover. But it is a distinct *condition*
    and the screen must say so. "오류가 발생했습니다" next to a raw provider JSON
    reads as "the system is broken"; the reality is "come back in 34 seconds",
    and on the free tier that is the normal end of a development session
    (20 requests per day per model, measured 2026-08-26).

    Collapsing it into a generic transient error is the same mistake as
    recording an unpriced call as free (BR-96) or an unverified sentence as
    supported (BR-87): two different facts written down as one.
    """

    def __init__(
        self, message: str, *, retry_after_seconds: float | None = None, detail: str | None = None
    ) -> None:
        super().__init__(message, detail=detail)
        self.retry_after_seconds = retry_after_seconds


# ---- Permanent (never retried, BR-42) ----
class PermanentError(SafeenvError):
    kind = FailureKind.PERMANENT


class SourceNotFoundError(PermanentError):
    """HTTP 4xx other than 429."""


class ExtractionError(PermanentError):
    """Text could not be extracted from the original document."""


class SchemaMismatchError(PermanentError):
    """Source response did not match the configured shape."""


class MissingRequiredMetadataError(PermanentError):
    """BR-32 — source_url or doc_type absent; the document is not indexed."""


class ApiKeyMissingError(PermanentError):
    """BR-02 — source requires an API key that is not configured."""


# ---- Policy blocked (never retried, never bypassed, BR-43/BR-04) ----
class PolicyBlockedError(SafeenvError):
    kind = FailureKind.POLICY_BLOCKED


class ConfigurationError(SafeenvError):
    """Raised at startup; not part of job item classification."""


class ValidationError(SafeenvError):
    """u5 - user input the person can fix, with a message meant for them.

    Separate from `ConfigurationError` because the audience differs: that one is
    for whoever deploys the system, this one is for whoever is filling in a
    form. A password policy failure and a missing API key are not the same event.
    """


class AuthenticationError(SafeenvError):
    """u5 - the credentials did not work.

    Carries no detail on purpose (BR-134). "No such account" and "wrong
    password" are the same error here, because telling them apart turns the
    login form into a way to check who has registered.
    """


class PermissionDeniedError(SafeenvError):
    """u5 - the caller does not own this.

    Callers translate it to **404**, not 403 (BR-146): 403 confirms the resource
    exists, and document ids are sequential.
    """


_HTTP_TRANSIENT = {408, 425, 429, 500, 502, 503, 504}


def classify_http_status(status: int) -> FailureKind:
    """Map an HTTP status onto a FailureKind (BR-41, BR-42)."""
    if status in _HTTP_TRANSIENT or status >= 500:
        return FailureKind.TRANSIENT
    if 400 <= status < 500:
        return FailureKind.PERMANENT
    return FailureKind.PERMANENT


def classify(error: BaseException) -> FailureKind:
    """C16.classify — pure classification of an exception (BR-41~43)."""
    if isinstance(error, SafeenvError):
        return error.kind
    if isinstance(error, TimeoutError | ConnectionError | OSError):
        return FailureKind.TRANSIENT
    return FailureKind.PERMANENT
