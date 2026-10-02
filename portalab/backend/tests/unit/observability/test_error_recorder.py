"""025 T009 — fingerprints are stable across volatile parts; messages and contexts are redacted."""

from portalab.modules.observability.errors.recorder import clean_message, fingerprint, normalize


def test_fingerprint_ignores_volatile_parts() -> None:
    a = fingerprint(
        "sync",
        "timeout",
        "TimeoutError",
        "service 0190f3c2-1111-7000-8000-000000000001 timed out after 31s at 10.0.0.5:8080",
    )
    b = fingerprint(
        "sync",
        "timeout",
        "TimeoutError",
        "service 0190f3c2-2222-7000-8000-000000000002 timed out after 12s at 10.0.0.9:8080",
    )
    c = fingerprint("sync", "timeout", "ValueError", "service x timed out")
    assert a == b and a != c
    assert normalize("user 'bob' id 42 at http://host/x") == "user <value> id <n> at <url>"


def test_messages_are_redacted() -> None:
    message = clean_message("login for jane@example.org failed: token=abcdef123456 Bearer zzzzzzzz")
    assert "jane@example.org" not in message and "abcdef123456" not in message and "zzzzzzzz" not in message
