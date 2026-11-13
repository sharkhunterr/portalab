"""Issue 247 — the archive's encryption: what goes in comes out with the passphrase; a wrong passphrase, a cut
or an altered archive is refused."""

import io
import json
import struct

import pytest

from portalab.modules.administration.backup.crypto import (
    CHUNK,
    MAGIC,
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


@pytest.mark.parametrize(
    "costs",
    [
        {"n": 2**24, "r": 8, "p": 1},
        {"n": 2**15, "r": 512, "p": 1},
        {"n": 2**15, "r": 8, "p": 64},
        {"n": 3000, "r": 8, "p": 1},
    ],
)
def test_a_forged_header_cannot_make_the_key_costly(costs: dict[str, int]) -> None:
    """Issue 405: scrypt's costs come from the archive itself, read before any proof — bounded."""
    header = json.dumps(
        {"kdf": "scrypt", **costs, "salt": "00" * 16, "nonce": "00" * 7, "chunk": CHUNK}
    ).encode()
    forged = io.BytesIO(MAGIC + struct.pack(">I", len(header)) + header)
    with pytest.raises(NotAnArchive):
        DecryptingReader(forged, "a long passphrase")


def test_a_chunk_cannot_claim_more_than_a_chunk() -> None:
    sink = io.BytesIO()
    writer = EncryptingWriter(sink, "a long passphrase")
    writer.write(b"hello")
    writer.close()
    data = bytearray(sink.getvalue())
    start = len(MAGIC) + 4 + struct.unpack(">I", data[len(MAGIC) : len(MAGIC) + 4])[0]
    data[start : start + 4] = struct.pack(">I", 2**31)  # a chunk claiming 2 GB
    with pytest.raises(NotAnArchive):
        DecryptingReader(io.BytesIO(bytes(data)), "a long passphrase")
