"""The archive's encryption (issue 247): a passphrase stretched with scrypt into an AES-256-GCM key, the
stream cut into chunks each sealed with its number and whether it is the last (a cut, reordered or altered
archive does not open). Nothing of the archive is readable without the passphrase, not even what it holds."""

import json
import os
import struct
from typing import IO, Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"PORTALAB-BACKUP\x01"
CHUNK = 1024 * 1024
SCRYPT = {"n": 2**15, "r": 8, "p": 1}
MIN_PASSPHRASE = 12


class WrongPassphrase(ValueError):
    """The passphrase does not open the archive (or the archive was altered)."""


class NotAnArchive(ValueError):
    """The file is not a Portalab backup (or a damaged one)."""


def _key(passphrase: str, salt: bytes, params: dict[str, int]) -> AESGCM:
    derived = Scrypt(salt=salt, length=32, n=params["n"], r=params["r"], p=params["p"]).derive(
        passphrase.encode("utf-8")
    )
    return AESGCM(derived)


def _nonce(prefix: bytes, counter: int, last: bool) -> bytes:
    return prefix + struct.pack(">IB", counter, 1 if last else 0)


class EncryptingWriter:
    """A write-only file object: what is written goes out encrypted, chunk by chunk, to ``sink``."""

    def __init__(self, sink: IO[bytes], passphrase: str) -> None:
        if len(passphrase) < MIN_PASSPHRASE:
            raise ValueError(f"the passphrase needs {MIN_PASSPHRASE} characters at least")
        salt, prefix = os.urandom(16), os.urandom(7)
        header = json.dumps(
            {"kdf": "scrypt", **SCRYPT, "salt": salt.hex(), "nonce": prefix.hex(), "chunk": CHUNK}
        ).encode()
        sink.write(MAGIC + struct.pack(">I", len(header)) + header)
        self._sink, self._aad, self._prefix = sink, MAGIC + header, prefix
        self._aead = _key(passphrase, salt, SCRYPT)
        self._buffer = bytearray()
        self._counter = 0
        self._closed = False

    def write(self, data: bytes) -> int:
        self._buffer += data
        while len(self._buffer) > CHUNK:
            self._seal(bytes(self._buffer[:CHUNK]), last=False)
            del self._buffer[:CHUNK]
        return len(data)

    def _seal(self, plain: bytes, *, last: bool) -> None:
        sealed = self._aead.encrypt(_nonce(self._prefix, self._counter, last), plain, self._aad)
        self._sink.write(struct.pack(">I", len(sealed)) + sealed)
        self._counter += 1

    def close(self) -> None:
        if not self._closed:
            self._seal(bytes(self._buffer), last=True)
            self._buffer.clear()
            self._closed = True

    def flush(self) -> None:  # tarfile flushes; chunks go out when full
        return None


class DecryptingReader:
    """A read-only file object over an archive: chunks opened in order, the last one required."""

    def __init__(self, source: IO[bytes], passphrase: str) -> None:
        if source.read(len(MAGIC)) != MAGIC:
            raise NotAnArchive("not a Portalab backup")
        (size,) = struct.unpack(">I", source.read(4))
        if size > 4096:
            raise NotAnArchive("damaged header")
        header = source.read(size)
        try:
            params: dict[str, Any] = json.loads(header)
            salt, prefix = bytes.fromhex(params["salt"]), bytes.fromhex(params["nonce"])
        except (ValueError, KeyError) as exc:
            raise NotAnArchive("damaged header") from exc
        self._source, self._aad, self._prefix = source, MAGIC + header, prefix
        self._aead = _key(passphrase, salt, {k: int(params[k]) for k in ("n", "r", "p")})
        self._buffer = bytearray()
        self._counter = 0
        self._ended = False
        self._fill()  # a wrong passphrase is told at once

    def _fill(self) -> None:
        raw = self._source.read(4)
        if len(raw) < 4:
            raise NotAnArchive("the archive is cut short")
        (size,) = struct.unpack(">I", raw)
        sealed = self._source.read(size)
        if len(sealed) < size:
            raise NotAnArchive("the archive is cut short")
        for last in (False, True):
            try:
                plain = self._aead.decrypt(_nonce(self._prefix, self._counter, last), sealed, self._aad)
            except InvalidTag:
                continue
            self._buffer += plain
            self._counter += 1
            self._ended = last
            return
        if self._counter == 0:
            raise WrongPassphrase("wrong passphrase")
        raise NotAnArchive("the archive was altered")

    def read(self, size: int = -1) -> bytes:
        while not self._ended and (size < 0 or len(self._buffer) < size):
            self._fill()
        if size < 0:
            size = len(self._buffer)
        out = bytes(self._buffer[:size])
        del self._buffer[:size]
        return out
