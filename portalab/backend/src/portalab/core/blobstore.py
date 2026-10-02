"""Binary object storage port + filesystem baseline (spec 002 research R12; S3-compatible stores later).

Keys are **content-addressed** (``<namespace>/<sha256>``): the same bytes give the same key, nothing about
the owner leaks into the key, and a replaced object is simply a different key whose predecessor is deleted.
Blobs are never served statically: modules stream them through authenticated, visibility-checked routes.
"""

import hashlib
import os
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import anyio

CHUNK_SIZE = 64 * 1024
_NAMESPACE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_KEY = re.compile(r"^([a-z][a-z0-9_-]{0,63})/([0-9a-f]{64})$")


class BlobNotFound(LookupError):
    pass


class InvalidBlobKey(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StoredBlob:
    key: str
    size: int
    content_type: str


def content_key(namespace: str, data: bytes) -> str:
    if not _NAMESPACE.fullmatch(namespace):
        raise InvalidBlobKey(f"invalid blob namespace {namespace!r}")
    return f"{namespace}/{hashlib.sha256(data).hexdigest()}"


def parse_key(key: str) -> tuple[str, str]:
    match = _KEY.fullmatch(key)
    if match is None:
        raise InvalidBlobKey("invalid blob key")
    return match.group(1), match.group(2)


class BlobStore(Protocol):
    async def put(self, namespace: str, data: bytes, *, content_type: str) -> StoredBlob: ...

    async def get(self, key: str) -> bytes: ...

    def stream(self, key: str) -> AsyncIterator[bytes]: ...

    async def exists(self, key: str) -> bool: ...

    async def delete(self, key: str) -> bool: ...


class FileSystemBlobStore:
    """Blobs under ``<root>/<namespace>/<aa>/<sha256>``; writes are atomic (temp file + rename)."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        namespace, digest = parse_key(key)
        return self.root / namespace / digest[:2] / digest

    async def put(self, namespace: str, data: bytes, *, content_type: str) -> StoredBlob:
        key = content_key(namespace, data)
        path = self._path(key)
        await anyio.to_thread.run_sync(_atomic_write, path, data)
        return StoredBlob(key=key, size=len(data), content_type=content_type)

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return await anyio.Path(path).read_bytes()
        except FileNotFoundError as exc:
            raise BlobNotFound(key) from exc

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        path = self._path(key)
        try:
            handle = await anyio.open_file(path, "rb")
        except FileNotFoundError as exc:
            raise BlobNotFound(key) from exc
        async with handle:
            while chunk := await handle.read(CHUNK_SIZE):
                yield chunk

    async def exists(self, key: str) -> bool:
        return await anyio.Path(self._path(key)).is_file()

    async def delete(self, key: str) -> bool:
        path = anyio.Path(self._path(key))
        try:
            await path.unlink()
        except FileNotFoundError:
            return False
        return True


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return  # content-addressed: identical bytes already stored
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    temporary.chmod(0o600)
    temporary.replace(path)
