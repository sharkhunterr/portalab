"""Operator commands (spec 020 T025, R10): ``portalab backup|restore`` and ``portalab migrate --status``.

Backup = a ``pg_dump`` custom-format archive of the database plus a tarball of ``DATA_DIR`` (blobs) and
a manifest. The PostgreSQL client tools come from ``PATH`` (or ``--pg-dump``/``--pg-restore``); in the Docker
deployment run them where the client exists. Credentials go through the environment, never on the command
line nor in output. There is no UI-triggered restore (OQ-96).
"""

import json
import os
import shutil
import subprocess
import tarfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

Runner = Callable[[Sequence[str], dict[str, str]], int]


class OperationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PgTarget:
    env: dict[str, str]
    database: str


def pg_target(database_url: str) -> PgTarget:
    url = make_url(database_url)
    env = {
        "PGHOST": url.host or "localhost",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "",
        "PGDATABASE": url.database or "",
    }
    if url.password:
        env["PGPASSWORD"] = str(url.password)
    return PgTarget(env, url.database or "")


def _run(command: Sequence[str], env: dict[str, str]) -> int:
    return subprocess.run(list(command), env={**os.environ, **env}, check=False).returncode  # noqa: S603


def _tool(name: str, override: str | None) -> str:
    path = override or shutil.which(name)
    if not path:
        raise OperationError(f"{name} not found: install the PostgreSQL client or pass --{name}")
    return path


def backup(
    database_url: str,
    data_dir: Path,
    output: Path,
    *,
    heads: set[str],
    pg_dump: str | None = None,
    runner: Runner = _run,
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    target = pg_target(database_url)
    dump = output / "database.dump"
    code = runner([_tool("pg_dump", pg_dump), "--format=custom", "--no-owner", f"--file={dump}"], target.env)
    if code != 0:
        raise OperationError(f"pg_dump failed with exit code {code}")
    blobs = output / "data.tar.gz"
    with tarfile.open(blobs, "w:gz") as archive:
        if data_dir.exists():
            archive.add(data_dir, arcname="data")
    manifest = {
        "format": "portalab.backup",
        "version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "schema_heads": sorted(heads),
        "files": ["database.dump", "data.tar.gz"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output


def restore(
    database_url: str, data_dir: Path, source: Path, *, pg_restore: str | None = None, runner: Runner = _run
) -> None:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "portalab.backup":
        raise OperationError("not a Portalab backup")
    target = pg_target(database_url)
    code = runner(
        [
            _tool("pg_restore", pg_restore),
            "--clean",
            "--if-exists",
            "--no-owner",
            f"--dbname={target.database}",
            str(source / "database.dump"),
        ],
        target.env,
    )
    if code != 0:
        raise OperationError(f"pg_restore failed with exit code {code}")
    with tarfile.open(source / "data.tar.gz", "r:gz") as archive:
        members = [m for m in archive.getmembers() if m.name == "data" or m.name.startswith("data/")]
        for member in members:
            if member.issym() or member.islnk() or ".." in Path(member.name).parts:
                raise OperationError("unsafe path in the data archive")
        data_dir.parent.mkdir(parents=True, exist_ok=True)
        for member in members:
            member.name = member.name.removeprefix("data").lstrip("/") or "."
        archive.extractall(data_dir, members=members, filter="data")
