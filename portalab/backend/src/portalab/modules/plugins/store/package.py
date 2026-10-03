"""Package store (T008; R4): a plugin package is a directory or a ``.zip`` with ``plugin.toml`` at its
root. Installing extracts it into ``plugins/installed/<key>/<version>/`` (never into the core environment),
records a SHA-256 over the normalized content (sorted relative paths and bytes) and keeps every version on
disk for rollback. Loading verifies the checksum again: a tampered package is refused."""

import hashlib
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from portalab.core.errors import ValidationFailed
from portalab.modules.plugins.manifest.schema import Manifest, parse_toml

MAX_PACKAGE_BYTES = 20 * 1024 * 1024
MAX_FILES = 500


class PackageError(ValidationFailed):
    default_code = "plugin.invalid_package"
    default_title = "Invalid plugin package"


@dataclass(frozen=True, slots=True)
class StoredPackage:
    manifest: Manifest
    path: Path
    sha256: str


def checksum(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode() + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def read_manifest(source: Path) -> Manifest:
    if source.is_dir():
        candidate = source / "plugin.toml"
        if not candidate.is_file():
            raise PackageError("The package has no plugin.toml at its root.")
        return parse_toml(candidate.read_text(encoding="utf-8"))
    if source.suffix == ".zip" and source.is_file():
        with zipfile.ZipFile(source) as archive:
            try:
                return parse_toml(archive.read("plugin.toml").decode("utf-8"))
            except KeyError as exc:
                raise PackageError("The package has no plugin.toml at its root.") from exc
    raise PackageError("A plugin package is a directory or a .zip file.")


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > MAX_FILES or sum(m.file_size for m in members) > MAX_PACKAGE_BYTES:
        raise PackageError("The package is too large.")
    for member in members:
        name = PurePosixPath(member.filename)
        if name.is_absolute() or ".." in name.parts or member.filename.startswith(("/", "\\")):
            raise PackageError("The package contains an unsafe path.")
    return members


class PackageStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def available(self) -> Path:
        return self.root / "available"

    @property
    def installed(self) -> Path:
        return self.root / "installed"

    def target(self, key: str, version: str) -> Path:
        return self.installed / key / version

    def extract(self, source: Path) -> StoredPackage:
        manifest = read_manifest(source)
        target = self.target(manifest.key, manifest.version)
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            files = [p for p in source.rglob("*") if p.is_file()]
            if len(files) > MAX_FILES or sum(p.stat().st_size for p in files) > MAX_PACKAGE_BYTES:
                raise PackageError("The package is too large.")
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            with zipfile.ZipFile(source) as archive:
                archive.extractall(target, members=_safe_members(archive))
        return StoredPackage(manifest, target, checksum(target))

    def verify(self, key: str, version: str, expected: str) -> Path:
        target = self.target(key, version)
        if not target.is_dir() or checksum(target) != expected:
            raise PackageError("The installed package does not match its checksum.", code="plugin.tampered")
        return target

    def packages_available(self) -> list[Path]:
        if not self.available.is_dir():
            return []
        return sorted(p for p in self.available.iterdir() if p.is_dir() or p.suffix == ".zip")
