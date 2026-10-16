"""Where visual packs live (``DATA_DIR/visuals``):

- ``inbox/``: what is waiting to be imported — folders and ``.zip`` files dropped there by hand, the uploads
  of the administration (``inbox/uploads/``) and the downloads from GitHub (``inbox/github/``);
- ``store/<pack>/<sha>/``: each imported version, extracted once and never changed (its files are served
  under that fingerprint, cached for good), kept for rollbacks.

The registry itself (sources, versions, reports, what is published) is in the database (``visuals`` schema);
the proof of concept's ``state.json`` is imported once, then renamed.

A zip may hold the pack in a sub-folder (a GitHub archive: ``<repo>-<ref>/…``): the folder with ``pack.json``
nearest the root is the pack. Paths leaving the pack, too many or too large files are refused.
"""

import hashlib
import io
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_BYTES = 20 * 1024 * 1024
MAX_FILES = 400
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_PATH = 200
S_IFLNK = 0o120000
ALLOWED = frozenset(
    {
        ".json", ".css", ".glsl", ".frag", ".js", ".mjs", ".md", ".txt",
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif",
        ".woff2", ".woff", ".ttf", ".otf",
        ".mp3", ".ogg", ".wav", ".webm", ".mp4",
    }
)  # fmt: skip


class PackageError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Files:
    """A pack's files, read from a folder or a zip: relative path → bytes (the pack folder as root)."""

    entries: dict[str, bytes]

    @property
    def sha(self) -> str:
        digest = hashlib.sha256()
        for name in sorted(self.entries):
            digest.update(name.encode() + b"\0" + self.entries[name] + b"\0")
        return digest.hexdigest()

    def get(self, name: str) -> bytes | None:
        return self.entries.get(name)


def _check(names_sizes: list[tuple[str, int]]) -> None:
    if len(names_sizes) > MAX_FILES:
        raise PackageError(f"too many files ({len(names_sizes)} > {MAX_FILES})")
    if sum(size for _, size in names_sizes) > MAX_BYTES:
        raise PackageError(f"too large (more than {MAX_BYTES // 1024 // 1024} MB)")
    for name, size in names_sizes:
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or "\0" in name
            or len(name) > MAX_PATH
            or any(ord(c) < 32 for c in name)
        ):
            raise PackageError(f"unsafe path: {name[:80]!r}")
        if size > MAX_FILE_BYTES:
            raise PackageError(f"file too large: {name} (more than {MAX_FILE_BYTES // 1024 // 1024} MB)")


def _root_of(names: list[str]) -> str:
    """The folder holding ``pack.json`` nearest the root ('' when at the root)."""
    candidates = sorted(
        (n for n in names if PurePosixPath(n).name == "pack.json"), key=lambda n: n.count("/")
    )
    if not candidates:
        raise PackageError("no pack.json found")
    parent = PurePosixPath(candidates[0]).parent.as_posix()
    return "" if parent == "." else parent + "/"


def read_zip(data: bytes, subdir: str = "") -> Files:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PackageError("not a zip file") from exc
    members = [m for m in archive.infolist() if not m.is_dir()]
    if any((m.external_attr >> 16) & 0o170000 == S_IFLNK for m in members):
        raise PackageError("an archive may not hold links")
    _check([(m.filename, m.file_size) for m in members])
    names = [m.filename for m in members]
    if subdir:
        top = names[0].split("/", 1)[0] + "/" if names and "/" in names[0] else ""
        prefix = f"{top}{subdir.strip('/')}/"
        names = [n for n in names if n.startswith(prefix)]
        if not names:
            raise PackageError(f"no folder {subdir!r} in the archive")
    root = _root_of(names)
    entries: dict[str, bytes] = {}
    for name in names:
        if not name.startswith(root) or name == root:
            continue
        data = archive.read(name)
        if len(data) > MAX_FILE_BYTES:  # an archive lying about its sizes
            raise PackageError(f"file too large: {name}")
        entries[name[len(root) :]] = data
    if sum(len(d) for d in entries.values()) > MAX_BYTES:
        raise PackageError(f"too large (more than {MAX_BYTES // 1024 // 1024} MB)")
    return Files(entries)


def read_folder(folder: Path) -> Files:
    # a link inside a dropped folder is never followed (it could point anywhere on the server)
    files = [
        p
        for p in folder.rglob("*")
        if p.is_file()
        and not p.name.startswith(".")
        and not any(q.is_symlink() for q in (p, *p.relative_to(folder).parents) if q != Path())
    ]
    _check([(p.relative_to(folder).as_posix(), p.stat().st_size) for p in files])
    root = _root_of([p.relative_to(folder).as_posix() for p in files])
    base = folder / root if root else folder
    return Files({p.relative_to(base).as_posix(): p.read_bytes() for p in files if base in p.parents})


def read_source(path: Path) -> Files:
    if path.is_dir():
        return read_folder(path)
    if path.suffix == ".zip" and path.is_file():
        return read_zip(path.read_bytes())
    raise PackageError("a pack is a folder or a .zip file")


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def inbox(self) -> Path:
        return self.root / "inbox"

    @property
    def state_file(self) -> Path:
        """The proof of concept's registry (imported once into the database)."""
        return self.root / "state.json"

    def folder(self, pack: str, sha: str) -> Path:
        return self.root / "store" / pack / sha[:16]

    def keep(self, pack: str, files: Files) -> Path:
        """Extracts a version once (a fingerprint already kept is left as it is)."""
        target = self.folder(pack, files.sha)
        if target.is_dir():
            return target
        staging = target.with_name(target.name + ".tmp")
        shutil.rmtree(staging, ignore_errors=True)
        for name, data in files.entries.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        staging.rename(target)
        return target

    def drop(self, pack: str, sha: str | None = None) -> None:
        """Deletes a version's files (a purged version), or all of a pack's (a pack removed for good)."""
        target = self.folder(pack, sha) if sha else self.root / "store" / pack
        if target.resolve().is_relative_to((self.root / "store").resolve()):
            shutil.rmtree(target, ignore_errors=True)

    def sources(self) -> list[Path]:
        """What waits in the inbox: its folders and zips, and those of its uploads and downloads."""
        if not self.inbox.is_dir():
            return []
        out: list[Path] = []
        for place in (self.inbox, self.inbox / "uploads", self.inbox / "github"):
            if not place.is_dir():
                continue
            for entry in sorted(place.iterdir()):
                if (entry.name in ("uploads", "github") and place == self.inbox) or entry.name.startswith(
                    "."
                ):
                    continue
                if entry.is_dir() or entry.suffix == ".zip":
                    out.append(entry)
        return out

    def file(self, pack: str, sha: str, name: str) -> Path | None:
        """A stored file (``None`` when outside the version's folder or missing)."""
        if "\0" in name or "\0" in pack or "\0" in sha:
            return None
        try:
            base = self.folder(pack, sha).resolve()
            path = (base / name).resolve()
        except (OSError, ValueError):
            return None
        if base not in path.parents or not path.is_file():
            return None
        return path
