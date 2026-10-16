"""Portalab's own packs (spec 028, US2): ``packs/builtin/`` shipped with each release, synchronised at start.

- A built-in version is reviewed with the release: it is published **without the workflow**, keeping the
  administrator's decisions (economy, the pack on or off) — a release never writes over a product of the
  catalog that already exists (``keep_existing``), and records « what changed » for the administration.
- The **first** synchronisation of a portal adopts what exists: every pack whose products the catalog already
  has is switched on, nothing of those products is touched (prices, texts, availability), owners, equipped
  looks and preferences keep their keys. A fresh portal gets the socle only (its first run, or the demo seed,
  switches the rest on).
- Afterwards, a pack new in a release arrives **switched off** (FR-008a); the socle is always on.

Idempotent: a version already known (same fingerprint) is skipped, so a start costs one read of the folders.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select

from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, NotFound, Unavailable
from portalab.modules.visuals.manifest import ManifestError, parse_pack
from portalab.modules.visuals.models import Element, Pack, PackVersion
from portalab.modules.visuals.service import SOCLE, VisualPackError, VisualPacks
from portalab.modules.visuals.store import Files, PackageError, read_folder

log = logging.getLogger(__name__)
SYSTEM = Principal(channel="system")
IMAGE_ROOT = Path("/app/packs/builtin")


def builtin_root(env: dict[str, str] | None = None) -> Path | None:
    """Where Portalab's own packs are: ``PORTALAB_BUILTIN_PACKS_DIR``, the image's folder, or the repository's
    (development)."""
    import os

    configured = (env if env is not None else os.environ).get("PORTALAB_BUILTIN_PACKS_DIR")
    if configured:
        return Path(configured)
    if IMAGE_ROOT.is_dir():
        return IMAGE_ROOT
    repository = Path(__file__).resolve().parents[5] / "packs" / "builtin"
    return repository if repository.is_dir() else None


@dataclass
class SyncReport:
    first: bool = False
    created: list[str] = field(default_factory=list)  # packs new to this portal
    updated: list[str] = field(default_factory=list)  # packs whose version changed
    unchanged: int = 0
    enabled: list[str] = field(default_factory=list)  # switched on by this synchronisation
    failed: dict[str, str] = field(default_factory=dict)

    def lines(self) -> list[str]:
        out = [f"first synchronisation: {'yes' if self.first else 'no'}"]
        out += [f"new: {p}" for p in self.created] + [f"updated: {p}" for p in self.updated]
        out += [f"switched on: {p}" for p in self.enabled]
        out += [f"failed: {p} ({why})" for p, why in self.failed.items()]
        out.append(f"unchanged: {self.unchanged}")
        return out


def _changes(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, list[str]]:
    def key(element: dict[str, Any]) -> str:
        return str(element.get("product") or f"{element['type']}:{element.get('look')}")

    old = {key(e): e for e in before}
    new = {key(e): e for e in after}
    return {
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "changed": sorted(k for k in set(old) & set(new) if old[k] != new[k]),
    }


class BuiltinSync:
    def __init__(self, packs: VisualPacks, root: Path | None) -> None:
        self.packs = packs
        self.root = root

    def folders(self) -> list[Path]:
        if self.root is None or not self.root.is_dir():
            return []
        return sorted(p for p in self.root.iterdir() if p.is_dir() and (p / "pack.json").is_file())

    async def run(self, actor: Principal = SYSTEM, *, dry_run: bool = False) -> SyncReport:
        report = SyncReport()
        folders = self.folders()
        if not folders:
            return report
        async with self.packs.database.session() as session:
            known = {
                row.id: row for row in (await session.execute(select(Pack).where(Pack.builtin))).scalars()
            }
            shas = {
                (v.pack_id, v.sha256)
                for v in (
                    await session.execute(  # the versions published (one that failed is tried again)
                        select(PackVersion).where(PackVersion.pack_id.in_(known), PackVersion.ever_published)
                    )
                ).scalars()
            }
        report.first = not known
        writer = self.packs._writer() if report.first and not dry_run else None
        for folder in folders:
            try:
                files = await asyncio.to_thread(read_folder, folder)
                manifest = parse_pack(files.get("pack.json") or b"")
            except (PackageError, ManifestError) as error:
                report.failed[folder.name] = str(error)[:200]
                continue
            if (manifest.id, files.sha) in shas:
                report.unchanged += 1
                continue
            (report.updated if manifest.id in known else report.created).append(manifest.id)
            if dry_run:
                continue
            try:
                await self._sync_one(actor, files, manifest.id, known.get(manifest.id), writer, report)
            except (VisualPackError, Conflict, NotFound, Unavailable) as error:
                report.failed[manifest.id] = str(error)[:200]
                log.warning("built-in pack %s not synchronised: %s", manifest.id, error)
        return report

    async def _sync_one(
        self,
        actor: Principal,
        files: Files,
        pack_id: str,
        holder: Pack | None,
        writer: Any,
        report: SyncReport,
    ) -> None:
        async with self.packs.database.unit_of_work() as uow:
            await self.packs._lock(uow.session)
            before: list[dict[str, Any]] = []
            if holder is not None and holder.current_version_id is not None:
                before = [
                    e.data
                    for e in (
                        await uow.session.execute(
                            select(Element).where(Element.version_id == holder.current_version_id)
                        )
                    ).scalars()
                ]
            imported = await self.packs._import(uow.session, files, {"kind": "builtin"}, builtin=True)
            version = (
                await uow.session.execute(
                    select(PackVersion).where(
                        PackVersion.pack_id == pack_id, PackVersion.version == imported.version
                    )
                )
            ).scalar_one()
            row = await uow.session.get(Pack, pack_id)
            assert row is not None
            if holder is not None and before:
                version.changes = _changes(before, version.report.get("elements", []))
            if holder is None and pack_id != SOCLE and writer is not None:
                # the first synchronisation of a portal: a pack whose products the catalog has is on
                keys = [e["product"] for e in version.report.get("elements", []) if e.get("product")]
                if keys and await writer.existing(keys):
                    row.state = "enabled"
                    report.enabled.append(pack_id)
        await self.packs.publish(actor, pack_id, imported.version, trusted=True)
