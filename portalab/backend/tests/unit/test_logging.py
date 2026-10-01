"""T009 — structured JSON logs with correlation id; secret-looking values redacted."""

import io
import json
import logging

import pytest

from portalab.core.logging import (
    configure_logging,
    correlation_scope,
    get_correlation_id,
    get_logger,
    redact,
    register_secret_value,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def stream() -> io.StringIO:
    buffer = io.StringIO()
    configure_logging("DEBUG", stream=buffer)
    return buffer


def _lines(buffer: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


def test_log_line_is_json_with_correlation_id(stream: io.StringIO) -> None:
    with correlation_scope("req-42"):
        get_logger("portalab.test").info("hello", extra={"fields": {"items": 3}})
    record = _lines(stream)[-1]
    assert record["message"] == "hello"
    assert record["correlation_id"] == "req-42"
    assert record["level"] == "INFO"
    assert record["logger"] == "portalab.test"
    assert record["items"] == 3
    assert "timestamp" in record


def test_correlation_scope_restores_previous_value() -> None:
    with correlation_scope("outer"):
        with correlation_scope("inner"):
            assert get_correlation_id() == "inner"
        assert get_correlation_id() == "outer"


@pytest.mark.parametrize(
    "secret_field",
    ["password", "api_key", "token", "SECRET_KEY", "authorization", "client_secret", "DATABASE_URL"],
)
def test_secret_fields_are_redacted(stream: io.StringIO, secret_field: str) -> None:
    get_logger("portalab.test").warning("connecting", extra={"fields": {secret_field: "s3cr3t-value"}})
    raw = stream.getvalue()
    assert "s3cr3t-value" not in raw
    assert _lines(stream)[-1][secret_field] == "***"


def test_secret_patterns_in_messages_are_redacted(stream: io.StringIO) -> None:
    log = get_logger("portalab.test")
    log.error("login failed password=hunter2 token: abcdef123456")
    log.error("upstream Authorization: Bearer eyJhbGciOi.payload.sig")
    log.error("db at postgresql+asyncpg://portalab:pa55word@db:5432/portalab")
    raw = stream.getvalue()
    for leaked in ("hunter2", "abcdef123456", "eyJhbGciOi.payload.sig", "pa55word"):
        assert leaked not in raw


def test_registered_secret_values_are_masked_everywhere(stream: io.StringIO) -> None:
    register_secret_value("very-unique-credential-987")
    get_logger("portalab.test").info("value is very-unique-credential-987 here")
    assert "very-unique-credential-987" not in stream.getvalue()
    assert redact({"nested": ["very-unique-credential-987"]}) == {"nested": ["***"]}


def test_exceptions_are_logged_redacted(stream: io.StringIO) -> None:
    try:
        raise ValueError("bad password=topsecret")
    except ValueError:
        get_logger("portalab.test").exception("boom")
    record = _lines(stream)[-1]
    assert "topsecret" not in stream.getvalue()
    assert "exception" in record


def test_level_filtering() -> None:
    buffer = io.StringIO()
    configure_logging("WARNING", stream=buffer)
    logging.getLogger("portalab.test").info("hidden")
    assert buffer.getvalue() == ""
