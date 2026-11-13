"""Issue 401 — a plugin package (.zip) that tries to write outside its folder, or is too big, is refused and
leaves nothing behind: a path climbing out, an absolute path, too many files, more bytes than allowed. The
archives are built here, at test time (never committed)."""

import io
import zipfile
from pathlib import Path

import pytest

from portalab.modules.plugins.store.package import MAX_FILES, MAX_PACKAGE_BYTES, PackageError, PackageStore

pytestmark = pytest.mark.unit
MANIFEST = 'key = "evil"\nname = "Evil"\nversion = "1.0.0"\n'


def archive(tmp_path: Path, files: dict[str, bytes]) -> Path:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as made:
        made.writestr("plugin.toml", MANIFEST)
        for name, data in files.items():
            made.writestr(name, data)
    path = tmp_path / "evil.zip"
    path.write_bytes(buffer.getvalue())
    return path


MALFORMED = {
    "climbing": {"../../outside.py": b"x"},
    "climbing deeper": {"evil_plugin/../../../outside.py": b"x"},
    "absolute": {"/tmp/outside.py": b"x"},  # noqa: S108 — the attack itself
    "backslash rooted": {"\\outside.py": b"x"},
    "too many files": {f"f{i}.txt": b"" for i in range(MAX_FILES + 1)},
    "too many bytes": {"big.bin": b"0" * (MAX_PACKAGE_BYTES + 1)},
}


@pytest.mark.parametrize("kind", sorted(MALFORMED))
def test_an_unsafe_package_is_refused_and_leaves_nothing(tmp_path: Path, kind: str) -> None:
    store = PackageStore(tmp_path / "plugins")
    with pytest.raises(PackageError):
        store.extract(archive(tmp_path, MALFORMED[kind]))
    assert not (tmp_path / "outside.py").exists() and not Path("/tmp/outside.py").exists()  # noqa: S108
    installed = store.target("evil", "1.0.0")
    assert not installed.exists() or not any(installed.rglob("*"))
