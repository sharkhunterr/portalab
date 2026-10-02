"""020 T025 — operator backup/restore wrappers: credentials only through the environment, manifest written,
unsafe archive paths refused."""

import io
import json
import tarfile
from collections.abc import Sequence
from pathlib import Path

import pytest

from portalab.app.cli import build_parser
from portalab.app.operations import OperationError, backup, pg_target, restore

pytestmark = pytest.mark.unit
URL = "postgresql+asyncpg://portalab:pw-secret-123@db:5432/portalab"


def test_target_keeps_password_out_of_arguments() -> None:
    target = pg_target(URL)
    assert target.env["PGPASSWORD"] == "pw-secret-123" and target.env["PGHOST"] == "db"


def test_backup_and_restore(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []

    def runner(command: Sequence[str], env: dict[str, str]) -> int:
        calls.append((list(command), env))
        for arg in command:
            if arg.startswith("--file="):
                Path(arg.removeprefix("--file=")).write_bytes(b"dump")
        return 0

    data = tmp_path / "data"
    (data / "blobs").mkdir(parents=True)
    (data / "blobs" / "a").write_text("blob")
    folder = backup(
        URL, data, tmp_path / "bk", heads={"core_0005"}, pg_dump="/usr/bin/pg_dump", runner=runner
    )
    assert json.loads((folder / "manifest.json").read_text())["schema_heads"] == ["core_0005"]
    assert all("pw-secret-123" not in " ".join(command) for command, _ in calls)
    target = tmp_path / "restored"
    restore(URL, target, folder, pg_restore="/usr/bin/pg_restore", runner=runner)
    assert (target / "blobs" / "a").read_text() == "blob"
    assert "--clean" in calls[-1][0]


def test_unsafe_archive_refused(tmp_path: Path) -> None:
    folder = tmp_path / "bk"
    folder.mkdir()
    (folder / "manifest.json").write_text(json.dumps({"format": "portalab.backup"}))
    with tarfile.open(folder / "data.tar.gz", "w:gz") as archive:
        info = tarfile.TarInfo("data/../../escape")
        payload = b"x"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    with pytest.raises(OperationError, match="unsafe"):
        restore(URL, tmp_path / "out", folder, pg_restore="/bin/true", runner=lambda c, e: 0)


def test_cli_exposes_operator_commands() -> None:
    parser = build_parser()
    assert parser.parse_args(["migrate", "--status"]).status is True
    assert parser.parse_args(["backup", "--output", "/tmp/x"]).output == "/tmp/x"  # noqa: S108
    assert parser.parse_args(["restore", "--input", "/b", "--yes"]).yes is True
