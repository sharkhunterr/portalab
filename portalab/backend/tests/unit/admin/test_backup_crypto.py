"""Issue 247 — the archive's encryption: what goes in comes out with the passphrase; a wrong passphrase, a cut
or an altered archive is refused."""

import io

import pytest

from portalab.modules.administration.backup.crypto import (
    CHUNK,
    DecryptingReader,
    EncryptingWriter,
    NotAnArchive,
    WrongPassphrase,
)

PASSPHRASE = "a long enough phrase"


def seal(data: bytes) -> bytes:
    sink = io.BytesIO()
    writer = EncryptingWriter(sink, PASSPHRASE)
    for start in range(0, len(data), 70_000):
        writer.write(data[start : start + 70_000])
    writer.close()
    return sink.getvalue()


def test_round_trip_over_several_chunks() -> None:
    data = bytes(range(256)) * (CHUNK // 64)  # four chunks and more
    sealed = seal(data)
    assert data[:64] not in sealed
    reader = DecryptingReader(io.BytesIO(sealed), PASSPHRASE)
    assert reader.read(10) + reader.read() == data


def test_refusals() -> None:
    sealed = seal(b"x" * (CHUNK + 10))
    with pytest.raises(WrongPassphrase):
        DecryptingReader(io.BytesIO(sealed), "not the passphrase")
    with pytest.raises(NotAnArchive):
        DecryptingReader(io.BytesIO(b"PK\x03\x04 a zip"), PASSPHRASE)
    with pytest.raises(NotAnArchive):  # the last chunk cut
        DecryptingReader(io.BytesIO(sealed[: len(sealed) - 8]), PASSPHRASE).read()
    with pytest.raises(NotAnArchive):  # the last chunk missing
        DecryptingReader(io.BytesIO(sealed[: len(sealed) - (4 + 10 + 16)]), PASSPHRASE).read()
    altered = bytearray(sealed)
    altered[-5] ^= 1
    with pytest.raises(NotAnArchive):
        DecryptingReader(io.BytesIO(bytes(altered)), PASSPHRASE).read()
    with pytest.raises(ValueError):
        EncryptingWriter(io.BytesIO(), "short")
