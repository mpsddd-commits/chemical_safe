"""C2 Logger — structured JSON logging with correlation and secret masking.

BR-57  every record is JSON with a correlation id
BR-58  pipeline stages log stage + duration_ms
BR-59  API keys and tokens are never written
BR-60  URLs and free text are masked before storage
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# BR-60 — query parameters and inline assignments that must never surface.
# The optional scheme group matters: "Authorization: Bearer abc123" would
# otherwise mask the word "Bearer" and leave the token in the clear.
_SECRET_PARAM = re.compile(
    r"(?i)\b(api[-_]?key|serviceKey|access[-_]?token|token|secret|password|pwd|authorization"
    # u5 - `Cookie: safeenv_session=<jwt>` matched none of the names above, and
    # the whole token sits in it.
    r"|set-cookie|cookie)"
    r"\s*[=:]\s*(?:(?:bearer|basic|token)\s+)?([^\s&\"',;]+)"
)
_MASK = "***"

# u5 - an argon2 hash is the stored credential. Not urgent on its own, but it
# has no reason to travel into a log file.
_ARGON2_HASH = re.compile(r"\$argon2[a-z]{0,2}\$\S+")

# u5 - an address is not a secret, but a file full of them is a list of who has
# registered. Kept partially readable so a support question stays traceable.
_EMAIL = re.compile(
    r"\b([A-Za-z0-9._%+-]{1,2})[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
)

# BR-59 — key names whose *value* must never be logged.
#
# Deliberately not a substring match: "token" as a substring would also hit
# `input_tokens` and `output_tokens`, which are exactly the numbers FR-41 exists
# to record. Exact names plus suffixes keeps that distinction.
_SECRET_KEY_NAMES = frozenset(
    {
        "api_key", "apikey", "servicekey", "service_key", "secret_key",
        "access_key", "private_key", "access_token", "refresh_token",
        "token", "secret", "password", "pwd", "passwd",
        "authorization", "auth", "credentials",
        # u5
        "cookie", "set_cookie", "password_hash", "jwt_secret", "csrf_token",
    }
)
# Deliberately NOT a bare "_key": `ref_key` is a document identifier and the
# single most useful field when diagnosing a failed job item. Masking it made
# `job_item_failed` logs unreadable - found in Build & Test.
_SECRET_KEY_SUFFIXES = ("_api_key", "_apikey", "_secret", "_token", "_password", "_pwd")

_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}


def mask_secrets(text: str) -> str:
    """Replace secret-looking values in a string (BR-59, BR-60, OP-2)."""
    masked = _SECRET_PARAM.sub(lambda m: f"{m.group(1)}={_MASK}", text)
    masked = _ARGON2_HASH.sub(_MASK, masked)
    return _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", masked)


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return mask_secrets(value)
    if isinstance(value, dict):
        return {k: (_MASK if _is_secret_key(k) else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_scrub(v) for v in value]
    return value


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in _SECRET_KEY_NAMES:
        return True
    return lowered.endswith(_SECRET_KEY_SUFFIXES)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": mask_secrets(record.getMessage()),
        }
        cid = _correlation_id.get()
        if cid:
            payload["correlation_id"] = cid
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                # A secret passed as a top-level `extra` field is the easiest way
                # to leak one, so it is checked here and not only inside dicts.
                payload[key] = _MASK if _is_secret_key(key) else _scrub(value)
        if record.exc_info:
            payload["exception"] = mask_secrets(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def bind(correlation_id: str) -> None:
    """Bind a request_id or job_id to the current context (BR-57)."""
    _correlation_id.set(correlation_id)


def current_correlation_id() -> str | None:
    return _correlation_id.get()


def configure(level: str = "INFO", log_dir: Path | None = None) -> None:
    """ID-14 — JSON to stdout, plus a rotating file when a log dir is writable."""
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(JsonFormatter())
    root.addHandler(stream)

    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                log_dir / "safeenv.log", maxBytes=20_000_000, backupCount=5, encoding="utf-8"
            )
            file_handler.setFormatter(JsonFormatter())
            root.addHandler(file_handler)
        except OSError:
            # A read-only or missing volume must not prevent startup.
            root.warning("log_dir_unavailable", extra={"log_dir": str(log_dir)})


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
