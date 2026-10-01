"""T045 — SecretBox: authenticated encryption with per-record nonce; failures are safe; never printed."""

import io
import json

import pytest

from portalab.core.logging import configure_logging, get_logger
from portalab.core.secrets import SecretBox, SecretDecryptError, SecretValue

pytestmark = pytest.mark.unit

KEY = b"k" * 48
OTHER_KEY = b"o" * 48


def test_round_trip() -> None:
    box = SecretBox(KEY)
    token = box.encrypt("s3cr3t-password", context="connectors.service:42:password")
    assert isinstance(token, str)
    assert "s3cr3t-password" not in token
    assert box.decrypt(token, context="connectors.service:42:password").reveal() == "s3cr3t-password"


def test_nonce_is_per_record() -> None:
    box = SecretBox(KEY)
    assert box.encrypt("same", context="c") != box.encrypt("same", context="c")


def test_wrong_key_fails_safely() -> None:
    token = SecretBox(KEY).encrypt("value-123456", context="c")
    with pytest.raises(SecretDecryptError) as excinfo:
        SecretBox(OTHER_KEY).decrypt(token, context="c")
    assert "value-123456" not in str(excinfo.value)


def test_context_binding_prevents_swapping_ciphertexts() -> None:
    box = SecretBox(KEY)
    token = box.encrypt("value-123456", context="service:1:password")
    with pytest.raises(SecretDecryptError):
        box.decrypt(token, context="service:2:password")


@pytest.mark.parametrize("garbage", ["", "not-base64!!", "djE6", "v9:AAAA"])
def test_garbage_tokens_fail_safely(garbage: str) -> None:
    with pytest.raises(SecretDecryptError):
        SecretBox(KEY).decrypt(garbage, context="c")


def test_short_key_is_rejected() -> None:
    with pytest.raises(ValueError):
        SecretBox(b"too-short")


def test_secret_value_is_never_printed_or_logged() -> None:
    secret = SecretValue("hunter2-hunter2")
    assert "hunter2" not in repr(secret)
    assert "hunter2" not in str(secret)
    assert "hunter2" not in f"{secret}"
    with pytest.raises(TypeError):
        json.dumps(secret)
    buffer = io.StringIO()
    configure_logging("INFO", stream=buffer)
    get_logger("portalab.test").info("value=%s raw=hunter2-hunter2", secret)
    assert "hunter2" not in buffer.getvalue()


def test_decrypted_values_are_registered_for_redaction() -> None:
    box = SecretBox(KEY)
    token = box.encrypt("decrypted-credential-xyz", context="c")
    box.decrypt(token, context="c")
    buffer = io.StringIO()
    configure_logging("INFO", stream=buffer)
    get_logger("portalab.test").info("leak attempt decrypted-credential-xyz")
    assert "decrypted-credential-xyz" not in buffer.getvalue()
