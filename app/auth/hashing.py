"""C51 PasswordHasher - FR-33, NFR-11, BR-131·BR-133·BR-134.

argon2id rather than bcrypt. NFR-11 allows either; argon2 is memory-hard, and
bcrypt silently truncates input past 72 bytes - a passphrase and its first 72
bytes hash identically, which is a trap that needs its own guard.

The algorithm is not configurable. Making it so would widen the attack surface
and buy nothing: there is one right answer here and it is already chosen.

No database, no network - this module is pure and its tests run without either
(NFR-28).
"""

from __future__ import annotations

import re

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.core.errors import ValidationError

MIN_LENGTH = 10
# BR-133 - three of four classes. No maximum: argon2 has no length trap, and a
# cap on password length is a cap on how strong a password may be.
_CLASSES = (
    re.compile(r"[a-z]"),
    re.compile(r"[A-Z]"),
    re.compile(r"[0-9]"),
    re.compile(r"[^A-Za-z0-9]"),
)
REQUIRED_CLASSES = 3

_hasher = _Argon2()

# BR-134 - verified against when the account does not exist, so that a missing
# account costs the same time as a wrong password. Without this the response
# time answers "is this address registered?" even when the message does not.
_DUMMY_HASH = _hasher.hash("safeenv-dummy-password-for-constant-time-login")


def validate_policy(password: str) -> None:
    """Raise with a message meant for the person typing it."""
    if len(password) < MIN_LENGTH:
        raise ValidationError(f"비밀번호는 {MIN_LENGTH}자 이상이어야 합니다.")
    classes = sum(1 for pattern in _CLASSES if pattern.search(password))
    if classes < REQUIRED_CLASSES:
        raise ValidationError(
            "비밀번호는 영문 대문자·소문자·숫자·기호 중 "
            f"{REQUIRED_CLASSES}종류 이상을 포함해야 합니다."
        )


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-ish time whether or not the account exists (BR-134).

    `stored=None` means "no such account", and the dummy hash is verified
    anyway. The result is discarded; the cost is the point.
    """
    target = stored or _DUMMY_HASH
    try:
        _hasher.verify(target, password)
    except (VerifyMismatchError, VerificationError):
        return False
    return stored is not None


def needs_rehash(stored: str) -> bool:
    """True when the stored hash used weaker parameters than current defaults."""
    return _hasher.check_needs_rehash(stored)
