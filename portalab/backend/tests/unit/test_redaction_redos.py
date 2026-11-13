"""Issue 401 — the redaction of logs and setting histories never holds the portal: a long text (a setting a
request sends) is redacted in linear time (the fuzzer found a quadratic pattern that held the event loop for
42 s), and credentials in URLs are still masked."""

import time

import pytest

from portalab.core.logging import MASK, redact, redact_text

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "text", ["a" * 200_000, "a://" * 50_000, "bearer " + "a" * 200_000, "password=" + " " * 200_000]
)
def test_a_long_text_is_redacted_quickly(text: str) -> None:
    started = time.perf_counter()
    redact({"values": [text]})
    assert time.perf_counter() - started < 1.0


def test_credentials_are_still_masked() -> None:
    assert redact_text("postgres://bob:hunter2@db:5432/x") == f"postgres://bob:{MASK}@db:5432/x"
    assert "s3cr3t-value" not in redact_text("password=s3cr3t-value; token abcdefgh123")


def test_an_audit_entry_keeps_no_nul_character_and_fits_its_columns() -> None:
    """Issue 401: what a request sends never makes its audit entry fail (a NUL, an overlong scope)."""
    from portalab.core.audit_port import AuditRecord, ResourceRef
    from portalab.modules.authz.audit.store import DatabaseAuditSink, bounded_context

    sink = DatabaseAuditSink(database=None, max_context_bytes=64)  # type: ignore[arg-type]
    values = sink._values(
        AuditRecord(
            action="search.reindex", actor=None, resource=ResourceRef("x\x00y", "id\x00" + "z" * 500),
            decision="allow", context={"scope": "s\x00" + "c" * 500, "k\x00": "v\x00" * 100},
        )
    )  # fmt: skip
    assert "\x00" not in values["resource_type"] + values["resource_id"] + values["scope"]
    assert len(values["resource_id"]) <= 128 and len(values["scope"]) <= 128
    assert "\x00" not in str(bounded_context({"k\x00": "v\x00"}, 4096))
    assert "\x00" not in str(values["context"])


def test_an_audit_entry_keeps_no_half_surrogate() -> None:
    """Issue 401: half a surrogate pair (valid JSON, refused by PostgreSQL) never fails an audit entry."""
    import json

    from portalab.modules.authz.audit.store import bounded_context

    context = bounded_context({"ideas": ["Y8-", chr(0xDA0C) + "x"]}, 4096)
    assert all(not 0xD800 <= ord(c) <= 0xDFFF for c in json.dumps(context, ensure_ascii=False))
