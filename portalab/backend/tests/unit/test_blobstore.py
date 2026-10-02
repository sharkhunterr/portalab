"""002 T005 — kernel BlobStore port, filesystem baseline: content-addressed keys, delete, stream."""

from pathlib import Path

import pytest

from portalab.core.blobstore import (
    BlobNotFound,
    FileSystemBlobStore,
    InvalidBlobKey,
    content_key,
    parse_key,
)

pytestmark = pytest.mark.unit


async def test_put_get_is_content_addressed(tmp_path: Path) -> None:
    store = FileSystemBlobStore(tmp_path)
    first = await store.put("avatars", b"hello", content_type="image/png")
    again = await store.put("avatars", b"hello", content_type="image/png")
    other = await store.put("avatars", b"world", content_type="image/png")
    assert first.key == again.key == content_key("avatars", b"hello")
    assert other.key != first.key
    assert first.size == 5
    assert await store.get(first.key) == b"hello"
    assert await store.exists(first.key)


async def test_stream_yields_all_bytes(tmp_path: Path) -> None:
    store = FileSystemBlobStore(tmp_path)
    data = bytes(range(256)) * 1000
    blob = await store.put("exports", data, content_type="application/zip")
    chunks = [chunk async for chunk in store.stream(blob.key)]
    assert len(chunks) > 1
    assert b"".join(chunks) == data


async def test_delete_removes_and_is_idempotent(tmp_path: Path) -> None:
    store = FileSystemBlobStore(tmp_path)
    blob = await store.put("avatars", b"x", content_type="image/png")
    assert await store.delete(blob.key) is True
    assert await store.delete(blob.key) is False
    assert not await store.exists(blob.key)
    with pytest.raises(BlobNotFound):
        await store.get(blob.key)
    with pytest.raises(BlobNotFound):
        async for _ in store.stream(blob.key):
            pass


@pytest.mark.parametrize(
    "key", ["../etc/passwd", "avatars/../../x", "Avatars/" + "a" * 64, "avatars/xyz", ""]
)
def test_keys_cannot_escape_the_root(key: str) -> None:
    with pytest.raises(InvalidBlobKey):
        parse_key(key)


def test_namespace_is_validated() -> None:
    with pytest.raises(InvalidBlobKey):
        content_key("../up", b"x")


async def test_files_are_private(tmp_path: Path) -> None:
    store = FileSystemBlobStore(tmp_path)
    blob = await store.put("avatars", b"secret-ish", content_type="image/png")
    namespace, digest = parse_key(blob.key)
    path = tmp_path / namespace / digest[:2] / digest
    assert path.stat().st_mode & 0o077 == 0
