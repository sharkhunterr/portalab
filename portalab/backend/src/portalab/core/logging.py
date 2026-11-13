"""Structured JSON logging with correlation ids and secret redaction (plan §7, Observability FR-031).

Log lines never contain secrets: values of secret-looking keys, secret patterns inside messages
(``password=…``, bearer tokens, credentials embedded in URLs) and explicitly registered secret values are
replaced by ``***``. The same :func:`redact` function is reused by errors, jobs and the secrets module.
"""

import json
import logging
import re
import sys
import threading
from collections import deque
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import IO, Any
from uuid import uuid4

MASK = "***"

_correlation_id: ContextVar[str | None] = ContextVar("portalab_correlation_id", default=None)

_SECRET_KEY_RE = re.compile(
    r"(pass(word|wd)?|secret|token|api[_-]?key|private[_-]?key|authorization|cookie|credential|"
    r"database[_-]?url|dsn|^key$|_key$|-key$)",
    re.IGNORECASE,
)
_MESSAGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # credentials embedded in URLs: scheme://user:password@host — issue 401: the scheme's length bounded, or a
    # long text without « :// » took quadratic time and held the whole portal (ReDoS)
    re.compile(
        r"(?P<prefix>\b[a-z][a-z0-9+.\-]{0,31}://[^\s:/@]{1,256}:)(?P<secret>[^\s@]{1,1024})(?P<suffix>@)",
        re.IGNORECASE,
    ),
    # Authorization headers / bearer tokens
    re.compile(r"(?P<prefix>\b(?:bearer|basic|token)\s+)(?P<secret>[A-Za-z0-9._~+/=\-]{6,})", re.IGNORECASE),
    # key=value or key: value pairs for secret-looking keys
    re.compile(
        r"(?P<prefix>\b(?:pass(?:word|wd)?|secret|token|api[_-]?key|client[_-]?secret|access[_-]?key|"
        r"authorization)\b\s*[=:]\s*[\"']?)(?P<secret>[^\s\"',;&]+)",
        re.IGNORECASE,
    ),
)
_registered_secrets: set[str] = set()


def register_secret_value(value: str) -> None:
    """Mask this exact value wherever it appears in logs, errors or redacted payloads."""
    if value and len(value) >= 6:
        _registered_secrets.add(value)


def is_secret_key(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(key))


def redact_text(text: str) -> str:
    for secret in _registered_secrets:
        if secret in text:
            text = text.replace(secret, MASK)
    for pattern in _MESSAGE_PATTERNS:
        text = pattern.sub(lambda m: f"{m.group('prefix')}{MASK}{m.groupdict().get('suffix') or ''}", text)
    return text


def redact(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact a value (mappings, sequences, strings)."""
    if key is not None and is_secret_key(key) and value is not None:
        return MASK
    if isinstance(value, Mapping):
        return {k: redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def new_correlation_id() -> str:
    return uuid4().hex


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_correlation_id(value: str | None) -> None:
    _correlation_id.set(value)


@contextmanager
def correlation_scope(value: str | None = None) -> Iterator[str]:
    """Bind a correlation id for the duration of a request/job (generated if absent)."""
    correlation = value or new_correlation_id()
    token = _correlation_id.set(correlation)
    try:
        yield correlation
    finally:
        _correlation_id.reset(token)


_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime", "fields"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line; structured fields via ``extra={"fields": {...}}``."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
            "correlation_id": get_correlation_id(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, Mapping):
            for k, v in redact(dict(fields)).items():
                payload.setdefault(str(k), v)
        for k, v in vars(record).items():
            if k not in _RESERVED and not k.startswith("_"):
                payload.setdefault(k, redact(v, key=k))
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


class LogTap(logging.Handler):
    """Issue 158: the last lines of this process, already redacted, kept for the log journal
    (``observability``) to store — bounded: under a flood the oldest lines waiting are dropped, never the
    process slowed. Lines of the journal itself are left out (it would feed on its own writes)."""

    IGNORED = ("portalab.modules.observability.logs", "sqlalchemy.engine")

    def __init__(self, capacity: int = 5_000) -> None:
        super().__init__(logging.INFO)
        self._lines: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self.dropped = 0
        self._json = JsonFormatter()

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(self.IGNORED):
            return
        try:
            line = json.loads(self._json.format(record))
        except Exception:  # never let a log line break the caller
            return
        with self._lock:
            if len(self._lines) == self._lines.maxlen:
                self.dropped += 1
            self._lines.append(line)

    def drain(self, limit: int = 1_000) -> list[dict[str, Any]]:
        with self._lock:
            taken = [self._lines.popleft() for _ in range(min(limit, len(self._lines)))]
        return taken


log_tap = LogTap()


def configure_logging(level: str = "INFO", *, stream: IO[str] | None = None) -> None:
    """Install the JSON handler on the root logger (idempotent), and the journal's tap (issue 158)."""
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    log_tap.setLevel(logging.DEBUG if level.upper() == "DEBUG" else logging.INFO)
    root.addHandler(log_tap)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
