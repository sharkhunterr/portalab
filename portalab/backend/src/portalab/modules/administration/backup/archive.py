"""Saving a whole portal and bringing it into a new installation (issue 247).

**Saving** reads every table the catalog keeps (``catalog.py``) from one consistent snapshot, each as
compressed CSV with its columns named, then writes one archive — the description (``manifest.json``: the
portal, its schema version, each table and how many rows, the folders), the portal's key (so the secrets can
be read again), the tables and the data folders — encrypted with a passphrase (``crypto.py``). The heavy part
(files, compression, encryption) runs off the event loop: the portal keeps answering while it saves.

**Restoring** opens the archive with its passphrase into a staging folder, checks it was saved by the same
schema version, then in **one transaction**: empties the tables it brings, creates the partitions they need,
loads each one (the triggers of append-only tables and the foreign keys set aside for the load, which needs
a PostgreSQL superuser role), sets the sequences after the highest value, and has each module encrypt its
secrets again with this portal's key. Only then are the data folders swapped in. Anything failing leaves the
portal as it was. The portal is restarted afterwards (its caches are those of the empty portal).
"""

import asyncio
import gzip
import io
import json
import os
import shutil
import tarfile
import tempfile
from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.administration import BACKUP_LEFT_OUT_CAPABILITY, SECRETS_REKEY_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.core.secrets import SecretBox
from portalab.modules.administration.backup.catalog import FOLDERS, SPLIT, category_of, folder_category
from portalab.modules.administration.backup.crypto import DecryptingReader, EncryptingWriter

log = get_logger(__name__)

FORMAT = 2  # the archive's own layout; each older one is read through its upgrader below
SUFFIX = ".plbackup"
COUNTED = {"identity.users": "members", "connectors.services": "services", "visuals.packs": "packs"}

Progress = Callable[[str, int, int], None]  # phase, done, total


class BackupError(ValueError):
    """A backup that cannot be made or restored, with a code the interface explains."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Options:
    history: bool = False  # the technical history (audit, metrics, logs, samples, technical events)
    media: bool = True  # the media images fetched from the services

    def keeps(self, category: str | None) -> bool:
        return (
            category == "data"
            or (category == "history" and self.history)
            or (category == "media" and self.media)
        )


@dataclass(slots=True)
class Table:
    name: str  # schema.table
    columns: list[str]
    rows: int = 0
    where: str | None = None


class Versions(Protocol):
    """The schema a backup carries against this portal's (``portalab.app.backup_versions``)."""

    async def current(self) -> set[str]: ...

    async def compare(self, archive_heads: Iterable[str]) -> str: ...

    async def prepare(self, archive_heads: Iterable[str]) -> None: ...

    async def finish(self) -> None: ...

    async def reset(self) -> None: ...


def _from_format_1(manifest: dict[str, Any]) -> dict[str, Any]:
    return {**manifest, "format": 2, "portalab": "unknown"}


UPGRADERS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {1: _from_format_1}


def upgrade_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """An archive's description in this version's layout: older layouts upgraded step by step, a newer one
    refused (made by a later Portalab: update this one first)."""
    version = manifest.get("format")
    if not isinstance(version, int) or version < 1:
        raise BackupError("backup.damaged", "This archive has no readable description.")
    if version > FORMAT:
        raise BackupError("backup.newer", "This archive was made by a later Portalab: update this one first.")
    while version < FORMAT:
        manifest = UPGRADERS[version](manifest)
        version = int(manifest["format"])
    return manifest


@dataclass(slots=True)
class Manifest:
    created_at: str
    heads: list[str]
    options: dict[str, bool]
    site: str
    tables: list[dict[str, Any]] = field(default_factory=list)
    partitions: list[dict[str, str]] = field(default_factory=list)
    folders: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    portalab: str = "unknown"  # the Portalab version that saved it
    format: int = FORMAT

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "portalab": self.portalab,
            "created_at": self.created_at,
            "heads": self.heads,
            "options": self.options,
            "site": self.site,
            "tables": self.tables,
            "partitions": self.partitions,
            "folders": self.folders,
            "counts": self.counts,
        }


def _quote(name: str) -> str:
    schema, table = name.split(".", 1)
    return f'"{schema}"."{table}"'


async def _driver(conn: Any) -> Any:
    raw = await conn.get_raw_connection()
    return raw.driver_connection


async def _tables(apg: Any) -> list[str]:
    rows = await apg.fetch(
        """
        SELECT n.nspname || '.' || c.relname AS name
          FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relkind IN ('r', 'p') AND NOT c.relispartition
           AND n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg\\_%'
         ORDER BY 1
        """
    )
    return [r["name"] for r in rows]


async def _columns(apg: Any, name: str) -> list[str]:
    rows = await apg.fetch(
        """
        SELECT attname FROM pg_attribute
         WHERE attrelid = $1::regclass AND attnum > 0 AND NOT attisdropped AND attgenerated = ''
         ORDER BY attnum
        """,
        _quote(name),
    )
    return [r["attname"] for r in rows]


async def _partitions(apg: Any) -> list[dict[str, str]]:
    rows = await apg.fetch(
        """
        SELECT pn.nspname || '.' || p.relname AS parent, cn.nspname || '.' || c.relname AS name,
               pg_get_expr(c.relpartbound, c.oid) AS bound
          FROM pg_inherits i
          JOIN pg_class c ON c.oid = i.inhrelid JOIN pg_namespace cn ON cn.oid = c.relnamespace
          JOIN pg_class p ON p.oid = i.inhparent JOIN pg_namespace pn ON pn.oid = p.relnamespace
         WHERE c.relkind IN ('r', 'p') AND c.relispartition
         ORDER BY 2
        """
    )
    return [{"parent": r["parent"], "name": r["name"], "bound": r["bound"]} for r in rows]


def _folders(data_dir: Path, options: Options) -> list[tuple[str, Path]]:
    """The data folders to save, as ``(name, path)`` — ``blobs`` taken one level down."""
    out: list[tuple[str, Path]] = []
    if not data_dir.is_dir():
        return out
    for entry in sorted(data_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        children = sorted(entry.iterdir()) if entry.name == "blobs" else [entry]
        for child in children:
            if not child.is_dir():
                continue
            name = child.relative_to(data_dir).as_posix()
            if options.keeps(folder_category(name)):
                out.append((name, child))
    return out


def _size(path: Path) -> tuple[int, int]:
    files = total = 0
    for root, _dirs, names in os.walk(path):
        for n in names:
            p = Path(root) / n
            if p.is_file() and not p.is_symlink():
                files += 1
                total += p.stat().st_size
    return files, total


# --- saving ------------------------------------------------------------------------------------------------
async def create(
    database: Database,
    data_dir: Path,
    secret_key: bytes,
    target: Path,
    passphrase: str,
    *,
    options: Options,
    heads: Iterable[str],
    site: str,
    portalab: str = "unknown",
    progress: Progress = lambda *_: None,
) -> Manifest:
    """Write the archive at ``target`` (through ``target.partial``); answers its description."""
    if len(passphrase) < 12:
        raise BackupError("backup.passphrase_short", "The passphrase needs 12 characters at least.")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".backup-", dir=target.parent))
    try:
        manifest = Manifest(
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            heads=sorted(heads),
            options={"history": options.history, "media": options.media},
            site=site,
            portalab=portalab,
        )
        async with database.engine.connect() as conn:
            apg = await _driver(conn)
            async with apg.transaction(isolation="repeatable_read", readonly=True):
                names = [n for n in await _tables(apg) if options.keeps(_kept(n))]
                manifest.partitions = await _partitions_of(apg, names)
                for index, name in enumerate(names):
                    progress("tables", index, len(names))
                    table = Table(name, await _columns(apg, name), where=_where(name, options))
                    table.rows = await _dump(apg, table, staging / f"{name}.csv.gz")
                    manifest.tables.append(
                        {"name": name, "columns": table.columns, "rows": table.rows, "where": table.where}
                    )
                    if name in COUNTED:
                        manifest.counts[COUNTED[name]] = table.rows
        folders = _folders(data_dir, options)
        for name, path in folders:
            files, size = await asyncio.to_thread(_size, path)
            manifest.folders.append({"name": name, "files": files, "bytes": size})
        await asyncio.to_thread(_write, target, passphrase, manifest, secret_key, staging, folders, progress)
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _kept(name: str) -> str | None:
    if name in SPLIT:
        return "data"  # its data rows at least
    return category_of(name)


def _where(name: str, options: Options) -> str | None:
    if name in SPLIT and not options.history:
        return SPLIT[name][0]
    return None


async def _partitions_of(apg: Any, names: list[str]) -> list[dict[str, str]]:
    """The partitions under the saved tables, parents before children."""
    found = await _partitions(apg)
    by_name = {p["name"]: p for p in found}
    kept = set(names)
    out: list[dict[str, str]] = []
    done: set[str] = set()

    def root(name: str) -> str:
        while name in by_name:
            name = by_name[name]["parent"]
        return name

    def visit(p: dict[str, str]) -> None:
        if p["name"] in done:
            return
        if p["parent"] in by_name:
            visit(by_name[p["parent"]])
        done.add(p["name"])
        out.append(p)

    for p in found:
        if root(p["name"]) in kept:
            visit(p)
    return out


async def _dump(apg: Any, table: Table, path: Path) -> int:
    columns = ", ".join(f'"{c}"' for c in table.columns)
    query = f"SELECT {columns} FROM {_quote(table.name)}"  # noqa: S608 — names read from the catalog
    if table.where:
        query += f" WHERE {table.where}"
    with gzip.open(path, "wb", compresslevel=6) as sink:

        async def write(data: bytes) -> None:
            sink.write(data)

        status = await apg.copy_from_query(query, output=write, format="csv", header=True)
    return int(str(status).rsplit(" ", 1)[-1] or 0)


def _write(
    target: Path,
    passphrase: str,
    manifest: Manifest,
    secret_key: bytes,
    staging: Path,
    folders: list[tuple[str, Path]],
    progress: Progress,
) -> None:
    partial = target.with_name(target.name + ".partial")
    total = sum(f["bytes"] for f in manifest.folders) or 1
    done = 0
    try:
        with partial.open("wb") as sink:
            writer = EncryptingWriter(sink, passphrase)
            with tarfile.open(fileobj=writer, mode="w|", format=tarfile.PAX_FORMAT) as tar:  # type: ignore[call-overload]
                _add_bytes(tar, "manifest.json", json.dumps(manifest.as_dict()).encode())
                _add_bytes(tar, "key", secret_key)
                for table in manifest.tables:
                    tar.add(staging / f"{table['name']}.csv.gz", arcname=f"tables/{table['name']}.csv.gz")
                for name, path in folders:
                    for root, dirs, files in os.walk(path):
                        dirs.sort()
                        for file in sorted(files):
                            full = Path(root) / file
                            if full.is_symlink() or not full.is_file():
                                continue
                            tar.add(full, arcname=f"files/{name}/{full.relative_to(path).as_posix()}")
                            done += full.stat().st_size
                            progress("files", done, total)
            writer.close()
        partial.replace(target)
        target.chmod(0o600)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def _add_bytes(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o600
    tar.addfile(info, io.BytesIO(data))


# --- reading -----------------------------------------------------------------------------------------------
def inspect(path: Path, passphrase: str) -> dict[str, Any]:
    """The archive's description, read with its passphrase (only its first entry is opened)."""
    with path.open("rb") as source:
        reader = DecryptingReader(source, passphrase)
        with tarfile.open(fileobj=reader, mode="r|") as tar:  # type: ignore[call-overload]
            member = tar.next()
            if member is None or member.name != "manifest.json":
                raise BackupError("backup.damaged", "This archive has no description.")
            handle = tar.extractfile(member)
            assert handle is not None
            manifest: dict[str, Any] = json.loads(handle.read())
    return upgrade_manifest(manifest)


def _unpack(path: Path, passphrase: str, staging: Path, progress: Progress) -> tuple[dict[str, Any], bytes]:
    manifest: dict[str, Any] = {}
    key = b""
    with path.open("rb") as source:
        size = os.fstat(source.fileno()).st_size or 1
        reader = DecryptingReader(source, passphrase)
        with tarfile.open(fileobj=reader, mode="r|") as tar:  # type: ignore[call-overload]
            for member in tar:
                if member.name == "manifest.json":
                    handle = tar.extractfile(member)
                    manifest = json.loads(handle.read()) if handle else {}
                    continue
                if member.name == "key":
                    handle = tar.extractfile(member)
                    key = handle.read() if handle else b""
                    continue
                if not member.isfile() or not member.name.startswith(("tables/", "files/")):
                    continue
                tar.extract(member, staging, filter="data")
                progress("reading", source.tell(), size)
    if len(key) < 32:
        raise BackupError("backup.damaged", "This archive is incomplete.")
    return upgrade_manifest(manifest), key


# --- restoring ---------------------------------------------------------------------------------------------
async def restore(
    database: Database,
    data_dir: Path,
    secret_key: bytes,
    archive: Path,
    passphrase: str,
    *,
    capabilities: CapabilityRegistry,
    versions: Versions,
    progress: Progress = lambda *_: None,
) -> dict[str, Any]:
    """Bring the archive into this portal; answers what was brought (tables, rows, secrets, folders).

    Saved by the same schema, it is loaded as it is; by an older one, this new portal is first brought back
    to that schema, then the loaded data migrated up to this version; by a newer one, it is refused."""
    await asyncio.to_thread(data_dir.mkdir, parents=True, exist_ok=True)  # a brand-new portal may lack it
    staging = Path(tempfile.mkdtemp(prefix=".restore-", dir=data_dir))
    prepared = False
    try:
        manifest, old_key = await asyncio.to_thread(_unpack, archive, passphrase, staging, progress)
        saved = manifest.get("heads", [])
        compatibility = await versions.compare(saved)
        if compatibility == "newer":
            raise BackupError(
                "backup.newer", "This archive was saved by a later Portalab: update this one first."
            )
        if compatibility == "older":
            progress("schema", 0, 1)
            prepared = True
            await versions.prepare(saved)
        result = await _load(
            database, staging / "tables", manifest, old_key, secret_key, capabilities, progress
        )
        if prepared:
            progress("upgrade", 0, 1)
            await versions.finish()
            prepared = False
        result["compatibility"] = compatibility
        result["portalab"] = manifest.get("portalab", "unknown")
        progress("files", 0, 1)
        result["folders"] = await asyncio.to_thread(_swap_folders, staging / "files", data_dir, manifest)
        progress("done", 1, 1)
        result["site"] = manifest.get("site", "")
        result["created_at"] = manifest.get("created_at", "")
        return result
    finally:
        if prepared:  # failed at the archive's schema: back to an empty portal of this version
            try:
                await versions.finish()
            except Exception:
                log.exception("the portal could not be migrated back after a failed restore")
        shutil.rmtree(staging, ignore_errors=True)


async def _gz_chunks(path: Path) -> AsyncIterator[bytes]:
    with gzip.open(path, "rb") as source:
        while chunk := source.read(1024 * 1024):
            yield chunk
            await asyncio.sleep(0)


async def _load(
    database: Database,
    tables_dir: Path,
    manifest: Mapping[str, Any],
    old_key: bytes,
    new_key: bytes,
    capabilities: CapabilityRegistry,
    progress: Progress,
) -> dict[str, Any]:
    async with database.engine.connect() as conn:
        apg = await _driver(conn)
        if not await apg.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"):
            raise BackupError(
                "backup.superuser",
                "Restoring needs the portal's PostgreSQL role to be a superuser (while it imports).",
            )
        await conn.begin()
        await conn.exec_driver_sql("SET LOCAL session_replication_role = replica")
        present = set(await _tables(apg))
        tables = [t for t in manifest["tables"] if t["name"] in present]
        skipped = [t["name"] for t in manifest["tables"] if t["name"] not in present]
        await _create_partitions(apg, manifest.get("partitions", []))
        if tables:
            await apg.execute("TRUNCATE " + ", ".join(_quote(t["name"]) for t in tables) + " CASCADE")
        rows = 0
        for index, table in enumerate(tables):
            progress("tables", index, len(tables))
            columns = await _columns(apg, table["name"])
            missing = [c for c in table["columns"] if c not in columns]
            if missing:
                raise BackupError("backup.version", f"{table['name']} differs from the saved one.")
            schema, name = table["name"].split(".", 1)
            await apg.copy_to_table(
                name,
                schema_name=schema,
                source=_gz_chunks(tables_dir / f"{table['name']}.csv.gz"),
                columns=table["columns"],
                format="csv",
                header=True,
            )
            rows += int(table.get("rows", 0))
        await _set_sequences(apg)
        session = AsyncSession(bind=conn, expire_on_commit=False)
        left_out = frozenset(
            name
            for name, category in FOLDERS.items()
            if category == "media" and not manifest["options"].get("media")
        )
        if left_out:
            for registration in capabilities.system_providers(BACKUP_LEFT_OUT_CAPABILITY):
                await registration.provider.left_out(session, left_out)
            await session.flush()
        secrets = await _rekey(conn, capabilities, SecretBox(old_key), SecretBox(new_key))
        await conn.commit()
    return {"tables": len(tables), "rows": rows, "skipped": skipped, "secrets": secrets}


async def _create_partitions(apg: Any, partitions: list[dict[str, str]]) -> None:
    present = {
        r["name"]
        for r in await apg.fetch(
            "SELECT n.nspname || '.' || c.relname AS name FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind IN ('r', 'p')"
        )
    }
    for p in partitions:  # parents first (as saved)
        if p["name"] in present or p["parent"] not in present:
            continue
        await apg.execute(f"CREATE TABLE {_quote(p['name'])} PARTITION OF {_quote(p['parent'])} {p['bound']}")
        present.add(p["name"])


async def _set_sequences(apg: Any) -> None:
    rows = await apg.fetch(
        """
        SELECT s.oid::regclass::text AS seq, t.oid::regclass::text AS tbl, a.attname AS col
          FROM pg_class s
          JOIN pg_depend d ON d.objid = s.oid AND d.deptype IN ('a', 'i')
          JOIN pg_class t ON t.oid = d.refobjid
          JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
         WHERE s.relkind = 'S' AND NOT t.relispartition
        """
    )
    for r in rows:
        highest = f'SELECT max("{r["col"]}") FROM {r["tbl"]}'  # noqa: S608 — names read from the catalog
        await apg.execute(f"SELECT setval($1::regclass, COALESCE(({highest}), 0) + 1, false)", r["seq"])


async def _rekey(
    conn: Any, capabilities: CapabilityRegistry, old: SecretBox, new: SecretBox
) -> dict[str, int]:
    done = failed = 0
    session = AsyncSession(bind=conn, expire_on_commit=False)
    for registration in capabilities.system_providers(SECRETS_REKEY_CAPABILITY):
        rewritten, unreadable = await registration.provider.rekey(session, old, new)
        done, failed = done + rewritten, failed + unreadable
    await session.flush()
    return {"rewritten": done, "unreadable": failed}


def clear_data(data_dir: Path) -> list[str]:
    """Issue 247: the data folders emptied for a new installation — the backups kept (to bring one back)."""
    cleared: list[str] = []
    if not data_dir.is_dir():
        return cleared
    for entry in sorted(data_dir.iterdir()):
        if entry.name == "backups":
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)
        cleared.append(entry.name)
    return cleared


def _swap_folders(files_dir: Path, data_dir: Path, manifest: Mapping[str, Any]) -> list[str]:
    swapped: list[str] = []
    for folder in manifest.get("folders", []):
        name = folder["name"]
        staged = files_dir / name
        live = data_dir / name
        live.parent.mkdir(parents=True, exist_ok=True)
        old = live.with_name(live.name + ".before-restore")
        if live.exists():
            shutil.rmtree(old, ignore_errors=True)
            live.rename(old)
        if staged.exists():
            staged.rename(live)
        else:
            live.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(old, ignore_errors=True)
        swapped.append(name)
    return swapped
