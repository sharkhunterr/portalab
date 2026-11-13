"""Error taxonomy → RFC 9457 ``application/problem+json`` (contracts/api-conventions.md).

Problems carry ``type``, ``title``, ``status``, ``detail``, ``instance`` plus a stable ``code`` and the
``correlation_id``. They never expose internals (exception class names, stack traces, connection strings)
or secrets: details pass through the shared redaction.
"""

from collections.abc import Mapping
from typing import Any, ClassVar

from portalab.core.logging import redact, redact_text

PROBLEM_CONTENT_TYPE = "application/problem+json"
PROBLEM_TYPE_BASE = "https://portalab.dev/problems/"

_CORE_FIELDS = frozenset({"type", "title", "status", "detail", "instance", "code", "correlation_id"})


class PortalError(Exception):
    """Base class of expected, user-facing failures."""

    status: ClassVar[int] = 500
    default_code: ClassVar[str] = "error"
    default_title: ClassVar[str] = "Error"

    def __init__(
        self,
        detail: str | None = None,
        *,
        code: str | None = None,
        title: str | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> None:
        self.detail = detail or self.default_title
        self.code = code or self.default_code
        self.title = title or self.default_title
        self.extensions = dict(extensions or {})
        super().__init__(self.detail)


class Unauthorized(PortalError):
    status = 401
    default_code = "unauthorized"
    default_title = "Authentication required"


class Forbidden(PortalError):
    status = 403
    default_code = "forbidden"
    default_title = "Not allowed"


class NotFound(PortalError):
    status = 404
    default_code = "not_found"
    default_title = "Not found"


class Conflict(PortalError):
    status = 409
    default_code = "conflict"
    default_title = "Conflict"


class ValidationFailed(PortalError):
    status = 422
    default_code = "validation_failed"
    default_title = "Validation failed"


class BadRequest(PortalError):
    status = 400
    default_code = "bad_request"
    default_title = "Bad request"


class Unavailable(PortalError):
    status = 503
    default_code = "unavailable"
    default_title = "Temporarily unavailable"


class Timeout(PortalError):
    status = 504
    default_code = "timeout"
    default_title = "Timed out"


def _problem(
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    correlation_id: str | None,
    instance: str | None,
    extensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    problem: dict[str, Any] = {
        "type": PROBLEM_TYPE_BASE + code,
        "title": title,
        "status": status,
        "detail": redact_text(detail),
        "instance": instance,
        "code": code,
        "correlation_id": correlation_id,
    }
    for key, value in redact(dict(extensions or {})).items():
        if key not in _CORE_FIELDS:
            problem[key] = value
    return problem


def to_problem(
    error: PortalError, *, correlation_id: str | None, instance: str | None = None
) -> dict[str, Any]:
    """Serialize an expected error as a problem document."""
    return _problem(
        status=error.status,
        code=error.code,
        title=error.title,
        detail=error.detail,
        correlation_id=correlation_id,
        instance=instance,
        extensions=error.extensions,
    )


def internal_error_problem(
    _error: BaseException, *, correlation_id: str | None, instance: str | None = None
) -> dict[str, Any]:
    """Generic problem for unexpected failures: nothing about the exception is exposed."""
    return _problem(
        status=500,
        code="internal_error",
        title="Internal error",
        detail="An unexpected error occurred. Quote the correlation id when reporting it.",
        correlation_id=correlation_id,
        instance=instance,
    )


INVALID_VALUE = "A value of the request is out of range or not allowed."
UNKNOWN_REFERENCE = "The request refers to something that does not exist."


def _sqlstate(error: BaseException) -> str:
    original = getattr(error, "orig", None)
    cause = getattr(original, "__cause__", None)
    return str(getattr(original, "sqlstate", None) or getattr(cause, "sqlstate", "") or "")


def database_problem(error: BaseException) -> PortalError | None:
    """Issue 401: what the database refused because of what a request sent — a number out of range, a NUL
    character, a reference to nothing, a duplicate — told as the request's fault (422/409), never as a
    server error. ``None`` for anything else (a real failure stays a 500)."""
    state = _sqlstate(error)
    if not state and "invalid input for query argument" in str(error):
        state = "22003"  # refused by the driver before it reached the server (a number out of range)
    if state.startswith("22") or state in ("23502", "23514"):
        return ValidationFailed(INVALID_VALUE, code="request.invalid_value")
    if state == "23503":
        return ValidationFailed(UNKNOWN_REFERENCE, code="request.unknown_reference")
    if state == "23505":
        return Conflict("This already exists.", code="request.duplicate")
    return None
