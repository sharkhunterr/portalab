"""T008 — PortalError → RFC 9457 problem+json (contracts/api-conventions.md)."""

import pytest

from portalab.core.errors import (
    Conflict,
    Forbidden,
    NotFound,
    PortalError,
    Timeout,
    Unauthorized,
    Unavailable,
    ValidationFailed,
    internal_error_problem,
    to_problem,
)

pytestmark = pytest.mark.unit

REQUIRED_FIELDS = {"type", "title", "status", "detail", "instance", "code", "correlation_id"}


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (Unauthorized(), 401, "unauthorized"),
        (Forbidden(), 403, "forbidden"),
        (NotFound(), 404, "not_found"),
        (Conflict(), 409, "conflict"),
        (ValidationFailed(), 422, "validation_failed"),
        (Unavailable(), 503, "unavailable"),
        (Timeout(), 504, "timeout"),
    ],
)
def test_each_error_maps_to_problem(error: PortalError, status: int, code: str) -> None:
    problem = to_problem(error, correlation_id="abc123", instance="/api/v1/x")
    assert problem.keys() >= REQUIRED_FIELDS
    assert problem["status"] == status
    assert problem["code"] == code
    assert problem["correlation_id"] == "abc123"
    assert problem["instance"] == "/api/v1/x"
    assert problem["type"].endswith(code)


def test_custom_code_and_detail() -> None:
    error = Conflict("Version mismatch for this resource.", code="config.version_conflict")
    problem = to_problem(error, correlation_id="c1")
    assert problem["code"] == "config.version_conflict"
    assert problem["detail"] == "Version mismatch for this resource."
    assert problem["status"] == 409


def test_extensions_are_included_but_cannot_override_core_fields() -> None:
    error = ValidationFailed(
        "Invalid fields.", extensions={"errors": [{"loc": ["body", "x"]}], "status": 200}
    )
    problem = to_problem(error, correlation_id="c2")
    assert problem["errors"] == [{"loc": ["body", "x"]}]
    assert problem["status"] == 422


def test_detail_never_leaks_secrets() -> None:
    error = Unavailable("upstream rejected password=hunter2 and token=abcdef123456")
    problem = to_problem(error, correlation_id="c3")
    assert "hunter2" not in problem["detail"]
    assert "abcdef123456" not in problem["detail"]


def test_internal_error_problem_has_no_internals() -> None:
    try:
        raise RuntimeError("database at postgresql://admin:s3cret@db:5432 exploded")
    except RuntimeError as exc:
        problem = internal_error_problem(exc, correlation_id="c4")
    assert problem["status"] == 500
    assert problem["code"] == "internal_error"
    serialized = repr(problem)
    assert "s3cret" not in serialized
    assert "postgresql://" not in serialized
    assert "RuntimeError" not in serialized
