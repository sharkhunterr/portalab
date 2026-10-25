"""The portal's backups (issue 247): the archives kept in ``<DATA_DIR>/backups``, one save or restore at a
time running in the background with its progress, an archive received from the browser written there as it
comes. Saving is audited; restoring is the arrival wizard's (a new portal, nobody signed in yet)."""

import asyncio
import re
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.logging import get_logger
from portalab.modules.administration.backup import archive
from portalab.modules.administration.backup.archive import SUFFIX, BackupError, Options
from portalab.modules.administration.backup.crypto import NotAnArchive, WrongPassphrase

log = get_logger(__name__)

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.plbackup$")


class BackupBusy(Conflict):
    default_code = "backup.busy"
    default_title = "A backup or a restore is already running"


class BackupRefused(ValidationFailed):
    default_code = "backup.refused"
    default_title = "The backup cannot be used"


@dataclass(slots=True)
class Run:
    kind: str  # "create" | "restore"
    state: str = "running"  # running | done | failed
    phase: str = "starting"
    done: int = 0
    total: int = 0
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    result: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "state": self.state,
            "phase": self.phase,
            "done": self.done,
            "total": self.total,
            "started_at": self.started_at,
            "result": self.result,
            "error": self.error,
        }


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "portalab"


class BackupService:
    def __init__(
        self,
        database: Database,
        data_dir: Path,
        secret_key: bytes,
        capabilities: CapabilityRegistry,
        audit: AuditSink,
        *,
        versions: archive.Versions,
        site: Callable[[], Awaitable[str]],
        portalab: str = "unknown",
    ) -> None:
        self.database = database
        self.data_dir = data_dir
        self.folder = data_dir / "backups"
        self._key = secret_key
        self.capabilities = capabilities
        self.audit = audit
        self.versions = versions
        self._site = site
        self.portalab = portalab
        self.run: Run | None = None
        self._task: asyncio.Task[None] | None = None

    # --- the archives ------------------------------------------------------------------------------------
    def archives(self) -> list[dict[str, Any]]:
        if not self.folder.is_dir():
            return []
        out = []
        for path in sorted(self.folder.glob(f"*{SUFFIX}"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = path.stat()
            out.append(
                {
                    "name": path.name,
                    "bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(timespec="seconds"),
                }
            )
        return out

    def path_of(self, name: str) -> Path:
        if not _NAME.fullmatch(name):
            raise NotFound("No such backup.", code="backup.not_found")
        path = self.folder / name
        if not path.is_file():
            raise NotFound("No such backup.", code="backup.not_found")
        return path

    async def delete(self, actor: Principal, name: str) -> None:
        path = self.path_of(name)
        path.unlink()
        await self._audit(actor, "admin.backup_deleted", {"name": name})

    async def receive(self, chunks: AsyncIterator[bytes]) -> str:
        """An archive sent from the browser, written as it comes (under a name of its own)."""
        self.folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        name = f"received-{stamp}-{secrets.token_hex(3)}{SUFFIX}"
        partial = self.folder / (name + ".partial")
        try:
            with partial.open("wb") as sink:
                async for chunk in chunks:
                    await asyncio.to_thread(sink.write, chunk)
            partial.replace(self.folder / name)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        return name

    async def inspect(self, name: str, passphrase: str) -> dict[str, Any]:
        path = self.path_of(name)
        try:
            manifest = await asyncio.to_thread(archive.inspect, path, passphrase)
        except WrongPassphrase as exc:
            raise BackupRefused("Wrong passphrase.", code="backup.wrong_passphrase") from exc
        except (NotAnArchive, BackupError) as exc:
            raise BackupRefused("This file is not a usable Portalab backup.", code="backup.damaged") from exc
        compatibility = await self.versions.compare(manifest.get("heads", []))
        return {
            "name": name,
            "site": manifest.get("site", ""),
            "portalab": manifest.get("portalab", "unknown"),
            "created_at": manifest.get("created_at", ""),
            "options": manifest.get("options", {}),
            "counts": manifest.get("counts", {}),
            "tables": len(manifest.get("tables", [])),
            "rows": sum(int(t.get("rows", 0)) for t in manifest.get("tables", [])),
            "folders": manifest.get("folders", []),
            "compatibility": compatibility,  # same | older (upgraded while imported) | newer (refused)
            "compatible": compatibility != "newer",
        }

    # --- running -----------------------------------------------------------------------------------------
    def state(self) -> dict[str, Any] | None:
        return self.run.as_dict() if self.run else None

    def _start(self, kind: str, work: Callable[[Run], Awaitable[dict[str, Any]]]) -> Run:
        if self.run is not None and self.run.state == "running":
            raise BackupBusy("A backup or a restore is already running.")
        run = Run(kind)
        self.run = run

        async def go() -> None:
            try:
                run.result = await work(run)
                run.state = "done"
            except (BackupError, WrongPassphrase, NotAnArchive) as exc:
                run.state = "failed"
                code = exc.code if isinstance(exc, BackupError) else "backup.damaged"
                if isinstance(exc, WrongPassphrase):
                    code = "backup.wrong_passphrase"
                run.error = {"code": code, "message": str(exc)}
            except Exception as exc:
                log.exception("backup run failed", extra={"fields": {"kind": kind}})
                run.state = "failed"
                run.error = {"code": "backup.failed", "message": type(exc).__name__}

        self._task = asyncio.create_task(go())
        return run

    def _progress(self, run: Run) -> Callable[[str, int, int], None]:
        def report(phase: str, done: int, total: int) -> None:
            run.phase, run.done, run.total = phase, done, total

        return report

    def start_create(self, actor: Principal, passphrase: str, options: Options) -> Run:
        if len(passphrase) < 12:
            raise BackupRefused(
                "The passphrase needs 12 characters at least.", code="backup.passphrase_short"
            )

        async def work(run: Run) -> dict[str, Any]:
            site = await self._site()
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
            target = self.folder / f"{_slug(site)}-{stamp}{SUFFIX}"
            manifest = await archive.create(
                self.database,
                self.data_dir,
                self._key,
                target,
                passphrase,
                options=options,
                heads=await self.versions.current(),
                site=site,
                portalab=self.portalab,
                progress=self._progress(run),
            )
            summary = {
                "name": target.name,
                "bytes": target.stat().st_size,
                "tables": len(manifest.tables),
                "counts": manifest.counts,
                "options": manifest.options,
            }
            await self._audit(actor, "admin.backup_created", summary)
            return summary

        return self._start("create", work)

    def start_restore(self, name: str, passphrase: str) -> Run:
        path = self.path_of(name)

        async def work(run: Run) -> dict[str, Any]:
            result = await archive.restore(
                self.database,
                self.data_dir,
                self._key,
                path,
                passphrase,
                capabilities=self.capabilities,
                versions=self.versions,
                progress=self._progress(run),
            )
            await self._audit(None, "admin.backup_restored", {"name": name, **result})
            return result

        return self._start("restore", work)

    async def _audit(self, actor: Principal | None, action: str, context: dict[str, Any]) -> None:
        try:
            async with self.database.unit_of_work() as uow:
                await self.audit.record(
                    uow.session, AuditRecord(action=action, actor=actor, context=context, sensitive=True)
                )
        except Exception:
            log.warning("backup audit not recorded", extra={"fields": {"action": action}})
