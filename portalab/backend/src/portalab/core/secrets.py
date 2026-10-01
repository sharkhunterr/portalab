"""Credential encryption at rest (research R11) and the write-only secret wrapper.

``SecretBox`` derives an AES-256-GCM key from the application key (``SECRET_KEY_FILE``) with HKDF and uses a
fresh random nonce per record. A ``context`` string (e.g. ``"connectors.service:<id>:password"``) is bound as
associated data, so a ciphertext copied onto another record does not decrypt. Decrypted values come back
wrapped in :class:`SecretValue` and are registered with the log redaction filter.
"""

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from portalab.core.logging import MASK, register_secret_value

TOKEN_PREFIX = "v1:"  # noqa: S105 — ciphertext format marker, not a secret
NONCE_BYTES = 12
MIN_KEY_BYTES = 32


class SecretDecryptError(ValueError):
    """The token cannot be decrypted (wrong key, tampering, wrong context or garbage). No detail exposed."""


class SecretValue:
    """Write-only secret: never printed, logged or JSON-serialized by accident."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value
        register_secret_value(value)

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"SecretValue('{MASK}')"

    def __str__(self) -> str:
        return MASK

    def __format__(self, spec: str) -> str:
        return MASK

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SecretValue) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __reduce__(self) -> tuple[object, ...]:
        raise TypeError("secrets cannot be pickled")


class SecretBox:
    def __init__(self, application_key: bytes) -> None:
        if len(application_key) < MIN_KEY_BYTES:
            raise ValueError(f"application key must be at least {MIN_KEY_BYTES} bytes")
        derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"portalab:secretbox:v1").derive(
            application_key
        )
        self._aead = AESGCM(derived)

    def encrypt(self, plaintext: str, *, context: str) -> str:
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = self._aead.encrypt(nonce, plaintext.encode("utf-8"), context.encode("utf-8"))
        return TOKEN_PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, token: str, *, context: str) -> SecretValue:
        if not token.startswith(TOKEN_PREFIX):
            raise SecretDecryptError("unsupported secret token")
        try:
            raw = base64.urlsafe_b64decode(token[len(TOKEN_PREFIX) :].encode("ascii"))
            if len(raw) <= NONCE_BYTES:
                raise SecretDecryptError("malformed secret token")
            plaintext = self._aead.decrypt(raw[:NONCE_BYTES], raw[NONCE_BYTES:], context.encode("utf-8"))
        except (InvalidTag, binascii.Error, ValueError, UnicodeError) as exc:
            raise SecretDecryptError("secret could not be decrypted") from exc
        return SecretValue(plaintext.decode("utf-8"))
