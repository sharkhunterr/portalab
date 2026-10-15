"""The registry of visual packs and their life: detected → analysed (``pending``) → validated and published
(``approved``) or ``rejected``; a published pack can be switched off and on again, and rolled back to a
version validated before.

POC: the registry is a JSON file (``DATA_DIR/visuals/state.json``) — no table, nothing to migrate; the real
module would keep it in its own schema. Publishing goes through ``marketplace.catalog_writer``: an element is
a shop product like any other, owned, equipped and refunded the usual way; switching a pack off takes its
products off sale (their owners keep them) and stops serving its files (each look falls back to the default).
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.visuals import CATALOG_WRITER, CatalogWriter, external_looks
from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, NotFound, Unavailable, ValidationFailed
from portalab.modules.ui.themes.definition import PACK_LOOKS
from portalab.modules.ui.visuals.analysis import analyse, looks_of
from portalab.modules.ui.visuals.github import GitHub, GitHubError, parse_address
from portalab.modules.ui.visuals.manifest import LOOK_FIELD, NOT_SOLD, ManifestError, parse_pack, version_key
from portalab.modules.ui.visuals.store import Files, PackageError, Store, read_source, read_zip

ECONOMY_FIELDS = ("price", "rarity", "level", "supply", "collection", "icon")
DEFAULT_COLLECTIONS = {
    "level_up": "levels",
    "level_badge": "levels",
    "effect": "celebrations",
    "ambient": "ambients",
    "profile_background": "ambients",
    "avatar_frame": "profile",
    "profile_banner": "profile",
    "name_style": "names",
    "notification_style": "looks",
    "notification_animation": "looks",
    "palette": "palettes",
    "badge": "badges",
    "title": "titles",
    "bundle": "packs",
    "booster": "boosters",
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class VisualPackError(ValidationFailed):
    default_code = "ui.visual_pack_invalid"
    default_title = "Invalid visual pack"


@dataclass(frozen=True, slots=True)
class Imported:
    pack: str
    version: str
    sha: str
    new: bool


class VisualPacks:
    def __init__(
        self,
        root: Path,
        capabilities: CapabilityRegistry,
        *,
        github: GitHub | None = None,
        themes: Any | None = None,
        audit: Callable[[Principal | None, str, dict[str, Any]], Awaitable[None]] | None = None,
        clock: Callable[[], str] = _now,
    ) -> None:
        self.audit = audit  # every action on a pack, in Portalab's audit log (sensitive)
        self.store = Store(root)
        self.themes = themes  # the interfaces' registry (``ThemeService``)
        self.capabilities = capabilities
        self.github = github or GitHub()
        self.clock = clock
        self._lock = asyncio.Lock()
        self.state: dict[str, Any] = self._load()
        self.refresh_looks()

    # --- the registry file -------------------------------------------------------------------------------
    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.store.state_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) and isinstance(data.get("packs"), dict) else {"packs": {}}
        except (OSError, ValueError):
            return {"packs": {}}

    def _save(self) -> None:
        self.store.root.mkdir(parents=True, exist_ok=True)
        staging = self.store.state_file.with_suffix(".tmp")
        staging.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8")
        staging.replace(self.store.state_file)

    def reload(self) -> None:
        """Reads the registry again (another process changed it) and the open vocabulary with it."""
        self.state = self._load()
        self.refresh_looks()

    def _pack(self, pack: str) -> dict[str, Any]:
        entry: dict[str, Any] | None = self.state["packs"].get(pack)
        if entry is None:
            raise NotFound("This visual pack is not known.", code="ui.visual_pack_not_found")
        return entry

    def _version(self, pack: str, version: str) -> dict[str, Any]:
        entry: dict[str, Any] | None = self._pack(pack)["versions"].get(version)
        if entry is None:
            raise NotFound("This version is not known.", code="ui.visual_pack_not_found")
        return entry

    # --- what is published ---------------------------------------------------------------------------------
    def live(self) -> list[tuple[str, dict[str, Any]]]:
        """The published versions of the packs switched on: (pack id, version entry)."""
        out = []
        for pack, entry in self.state["packs"].items():
            current = entry.get("current")
            if current and entry.get("enabled", True) and current in entry["versions"]:
                out.append((pack, entry["versions"][current]))
        return out

    def refresh_looks(self) -> None:
        by_type: dict[str, list[str]] = {}
        for _, version in self.live():
            for kind, look in looks_of(version["report"]):
                by_type.setdefault(kind, []).append(look)
        external_looks.replace(by_type)

    def _taken(self, except_pack: str) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
        """The looks and products the other packs published (their current versions)."""
        looks: dict[tuple[str, str], str] = {}
        products: dict[str, str] = {}
        for pack, entry in self.state["packs"].items():
            if pack == except_pack or not entry.get("current"):
                continue
            report = entry["versions"].get(entry["current"], {}).get("report", {})
            for kind, look in looks_of(report):
                looks[(kind, look)] = pack
            for element in report.get("elements", []):
                products[element["product"]] = pack
        return looks, products

    async def _audited(self, actor: Principal | None, action: str, **context: Any) -> None:
        if self.audit is not None:
            await self.audit(actor, f"visuals.{action}", context)

    # --- import ------------------------------------------------------------------------------------------
    def _import(self, files: Files, source: dict[str, Any]) -> Imported:
        raw = files.get("pack.json")
        if raw is None:
            raise VisualPackError("The pack has no pack.json.", code="ui.visual_pack_invalid")
        try:
            pack = parse_pack(raw)
        except ManifestError as error:
            raise VisualPackError(str(error)) from error
        sha = files.sha
        entry = self.state["packs"].setdefault(
            pack.id, {"versions": {}, "current": None, "enabled": True, "source": source}
        )
        entry["source"] = source
        known = entry["versions"].get(pack.version)
        if known and known["sha"] == sha:
            return Imported(pack.id, pack.version, sha, False)
        if known and known.get("status") == "approved":
            # a published version is never changed in place: the same number with other content is refused
            raise Conflict(
                f"Version {pack.version} of « {pack.id} » is already published with other files: "
                "give the new content a new version number.",
                code="ui.visual_pack_version_taken",
            )
        folder = self.store.keep(pack.id, files)
        looks, products = self._taken(pack.id)
        entry["versions"][pack.version] = {
            "sha": sha,
            "folder": str(folder.relative_to(self.store.root)),
            "detected_at": self.clock(),
            "status": "pending",
            "report": analyse(files, taken=looks, products_taken=products),
            "simulation": None,
            "decision": None,
        }
        return Imported(pack.id, pack.version, sha, True)

    async def scan(self, actor: Principal | None = None) -> dict[str, Any]:
        """The inbox read again: every folder and zip there, new ones (or new versions) analysed."""
        async with self._lock:
            found: list[dict[str, Any]] = []
            for path in self.store.sources():
                try:
                    files = await asyncio.to_thread(read_source, path)
                    imported = self._import(files, {"kind": "inbox", "path": path.name})
                    found.append({"source": path.name, **asdict(imported)})
                except (PackageError, VisualPackError, Conflict) as error:
                    found.append({"source": path.name, "error": str(error)})
            self._save()
        fresh = [f"{f['pack']}@{f['version']}" for f in found if f.get("new")]
        await self._audited(actor, "scanned", imported=fresh)
        return {"found": found}

    async def upload(self, filename: str, data: bytes, actor: Principal | None = None) -> Imported:
        """A zip sent from the administration: kept in the inbox (``uploads/``), then imported."""
        async with self._lock:
            try:
                files = read_zip(data)
            except PackageError as error:
                raise VisualPackError(str(error)) from error
            uploads = self.store.inbox / "uploads"
            uploads.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)[:80] or "pack.zip"
            (uploads / (safe if safe.endswith(".zip") else f"{safe}.zip")).write_bytes(data)
            imported = self._import(files, {"kind": "upload", "path": safe})
            self._save()
        await self._audited(actor, "uploaded", pack=imported.pack, version=imported.version, sha=imported.sha)
        return imported

    async def from_github(self, url: str, actor: Principal | None = None) -> Imported:
        """A pack on GitHub: the version it offers is downloaded, kept in the inbox and imported."""
        try:
            repository = parse_address(url)
            offer = await self.github.offer(repository)
            data = await self.github.download(repository, offer.ref)
            files = read_zip(data, repository.folder)
        except (GitHubError, PackageError) as error:
            raise VisualPackError(str(error), code="ui.visual_pack_source") from error
        async with self._lock:
            downloads = self.store.inbox / "github"
            downloads.mkdir(parents=True, exist_ok=True)
            (downloads / f"{offer.pack}-{offer.version}.zip").write_bytes(data)
            imported = self._import(files, {"kind": "github", "url": repository.url})
            self._pack(imported.pack)["remote"] = {
                "version": offer.version,
                "ref": offer.ref,
                "release": offer.release,
                "checked_at": self.clock(),
            }
            self._save()
        await self._audited(
            actor, "downloaded", pack=imported.pack, version=imported.version, sha=imported.sha, url=url
        )
        return imported

    async def check_updates(self) -> list[dict[str, Any]]:
        """For each pack from GitHub: the version it offers now, and whether it is newer than ours."""
        out: list[dict[str, Any]] = []
        for pack, entry in list(self.state["packs"].items()):
            source = entry.get("source") or {}
            if source.get("kind") != "github":
                continue
            try:
                offer = await self.github.offer(parse_address(source["url"]))
            except (GitHubError, KeyError) as error:
                out.append({"pack": pack, "error": str(error)})
                continue
            entry["remote"] = {
                "version": offer.version,
                "ref": offer.ref,
                "release": offer.release,
                "checked_at": self.clock(),
            }
            newest = max(entry["versions"], key=version_key, default=None)
            newer = newest is None or version_key(offer.version) > version_key(newest)
            out.append({"pack": pack, "offered": offer.version, "installed": newest, "update": newer})
        async with self._lock:
            self._save()
        return out

    # --- simulation ----------------------------------------------------------------------------------------
    def record_simulation(self, pack: str, version: str, results: list[dict[str, Any]]) -> None:
        """What the sandbox measured in a real browser: compiled or not, frames per second, errors."""
        entry = self._version(pack, version)
        entry["simulation"] = {"at": self.clock(), "results": results[:200]}
        self._save()

    # --- decisions -----------------------------------------------------------------------------------------
    def _writer(self) -> CatalogWriter:
        providers = self.capabilities.system_providers(CATALOG_WRITER)
        if not providers:
            raise Unavailable("The shop is not available.", code="ui.visual_pack_shop_unavailable")
        writer: CatalogWriter = providers[0].provider
        return writer

    @staticmethod
    def product_of(element: dict[str, Any], decided: dict[str, Any]) -> dict[str, Any]:
        """The shop entry of an element: what it proposes, as the administrator decided."""
        economy = {**element["economy"], **{k: v for k, v in decided.items() if k in ECONOMY_FIELDS}}
        payload = dict(element.get("payload") or {})
        field = LOOK_FIELD.get(element["type"])
        if field and element.get("look"):
            payload[field] = element["look"]
        return {
            "key": element["product"],
            "type": element["type"],
            "price": economy.get("price"),
            "rarity": economy.get("rarity") or "common",
            "names": {k: v for k, v in element["names"].items() if v},
            "descriptions": {k: v for k, v in element["descriptions"].items() if v},
            "payload": payload,
            "collection": economy.get("collection") or DEFAULT_COLLECTIONS.get(element["type"], "looks"),
            "icon": economy.get("icon"),
            "featured": False,
            "level": economy.get("level"),
            "supply": economy.get("supply"),
            "limit": None,
            "repeatable": bool(economy.get("repeatable")),
            "reward_only": economy.get("price") is None and element["type"] != "bundle",
        }

    async def _interface(self, actor: Principal, pack: str, entry: dict[str, Any], element: dict[str, Any], *,
                         enabled: bool) -> None:  # fmt: skip
        """An interface (element ``theme``) in the registry of interfaces: registered, or its definition
        updated (only one this pack brought), switched on or off with its pack."""
        if self.themes is None or element["type"] != "theme":
            return
        if not enabled:
            try:
                await self.themes.update(actor, element["look"], enabled=False)
            except Exception:  # an interface already gone, or the portal's default: left as it is
                return
            return
        path = self.store.file(pack, entry["sha"], f"{element['folder']}/{element['render']['file']}")
        if path is None:
            raise VisualPackError("The interface's definition is missing.")
        document = json.loads(path.read_text(encoding="utf-8"))
        token = PACK_LOOKS.set(frozenset(looks_of(entry["report"])))
        try:
            try:
                existing = await self.themes.get(element["look"])
            except NotFound:
                existing = None
            if existing is None:
                await self.themes.register(actor, document, source=f"visuals:{pack}", owner=f"visuals:{pack}")
            elif str(existing.source).startswith(f"visuals:{pack}"):
                await self.themes.update(actor, element["look"], definition=document)
            else:
                raise Conflict(f"An interface « {element['look']} » already exists outside this pack.")
            await self.themes.update(actor, element["look"], enabled=True)
        finally:
            PACK_LOOKS.reset(token)

    async def approve(
        self,
        actor: Principal,
        pack: str,
        version: str,
        decisions: dict[str, dict[str, Any]],
        *,
        accept_script: bool = False,
    ) -> dict[str, Any]:
        """Validates a version: its elements published in the shop with the economy decided (each element's
        proposal where nothing was changed), the version becomes the pack's current one, switched on."""
        async with self._lock:
            entry = self._version(pack, version)
            report = entry["report"]
            if not report["summary"]["publishable"]:
                raise VisualPackError("This version has blocking problems.", code="ui.visual_pack_blocked")
            if report["summary"]["script"] and not accept_script:
                raise VisualPackError(
                    "This version runs scripts in every member's page: confirm it explicitly.",
                    code="ui.visual_pack_script",
                )
            looks, products = self._taken(pack)
            clash = [e["product"] for e in report["elements"] if e["product"] in products] + [
                f"{kind}:{look}" for kind, look in looks_of(report) if (kind, look) in looks
            ]
            if clash:
                raise Conflict(f"Taken by another pack since the analysis: {', '.join(clash)}")
            writer = self._writer()
            outcomes: dict[str, str] = {}
            previous = {d: dict(v) for d, v in (entry.get("decision") or {}).get("economy", {}).items()}
            for element in report["elements"]:
                await self._interface(actor, pack, entry, element, enabled=True)
                if element["type"] in NOT_SOLD:  # a navigation: an interface wears it, nobody buys it
                    continue
                decided = {**previous.get(element["product"], {}), **decisions.get(element["product"], {})}
                outcomes[element["product"]] = await writer.publish(actor, self.product_of(element, decided))
                previous[element["product"]] = decided
            holder = self._pack(pack)
            old = holder.get("current")
            if old and old != version:
                former = holder["versions"][old]["report"]["elements"]
                gone = {e["product"] for e in former if e["type"] not in NOT_SOLD} - set(outcomes)
                for key in gone:  # an element the new version no longer has leaves the shop
                    await writer.withdraw(actor, key)
            entry["status"] = "approved"
            entry["decision"] = {
                "by": str(actor.user_id) if actor.user_id else None,
                "at": self.clock(),
                "economy": previous,
                "script_accepted": bool(report["summary"]["script"]),
            }
            holder["current"] = version
            holder["enabled"] = True
            self._save()
            self.refresh_looks()
        await self._audited(
            actor,
            "approved",
            pack=pack,
            version=version,
            sha=entry["sha"],
            script=bool(report["summary"]["script"]),
            economy=previous,
        )
        return {"pack": pack, "version": version, "products": outcomes}

    async def reject(
        self, pack: str, version: str, reason: str | None = None, actor: Principal | None = None
    ) -> None:
        async with self._lock:
            entry = self._version(pack, version)
            if self._pack(pack).get("current") == version:
                raise Conflict("This version is published: switch the pack off or roll it back instead.")
            entry["status"] = "rejected"
            entry["decision"] = {"at": self.clock(), "reason": (reason or "")[:500]}
            self._save()
        await self._audited(actor, "rejected", pack=pack, version=version, reason=(reason or "")[:500])

    async def switch(self, actor: Principal, pack: str, enabled: bool) -> None:
        """Off: its products leave the shop (owners keep them), its files are no longer served. On: back."""
        async with self._lock:
            holder = self._pack(pack)
            current = holder.get("current")
            if not current:
                raise Conflict("This pack has no published version.")
            writer = self._writer()
            version = holder["versions"][current]
            economy = (version.get("decision") or {}).get("economy", {})
            for element in version["report"]["elements"]:
                await self._interface(actor, pack, version, element, enabled=enabled)
                if element["type"] in NOT_SOLD:
                    continue
                if enabled:
                    product = self.product_of(element, economy.get(element["product"], {}))
                    await writer.publish(actor, product)
                else:
                    await writer.withdraw(actor, element["product"])
            holder["enabled"] = enabled
            self._save()
            self.refresh_looks()
        await self._audited(actor, "switched_on" if enabled else "switched_off", pack=pack, version=current)

    async def rollback(self, actor: Principal, pack: str, version: str) -> dict[str, Any]:
        """Back to a version validated before, with the economy decided then."""
        entry = self._version(pack, version)
        if entry.get("status") != "approved":
            raise Conflict("Only a version validated before can be rolled back to.")
        await self._audited(actor, "rolled_back", pack=pack, version=version)
        return await self.approve(actor, pack, version, {}, accept_script=True)

    # --- reading -------------------------------------------------------------------------------------------
    def listing(self) -> list[dict[str, Any]]:
        out = []
        for pack, entry in sorted(self.state["packs"].items()):
            versions = sorted(entry["versions"].items(), key=lambda kv: version_key(kv[0]), reverse=True)
            out.append(
                {
                    "id": pack,
                    "source": entry.get("source"),
                    "current": entry.get("current"),
                    "enabled": entry.get("enabled", True),
                    "remote": entry.get("remote"),
                    "versions": [
                        {
                            "version": number,
                            "sha": v["sha"][:16],
                            "status": v["status"],
                            "detected_at": v.get("detected_at"),
                            "summary": v["report"]["summary"],
                            "names": (v["report"].get("pack") or {}).get("names"),
                            "author": (v["report"].get("pack") or {}).get("author"),
                            "license": (v["report"].get("pack") or {}).get("license"),
                            "decision": v.get("decision"),
                            "simulated": bool(v.get("simulation")),
                        }
                        for number, v in versions
                    ],
                }
            )
        return out

    def detail(self, pack: str, version: str) -> dict[str, Any]:
        entry = self._version(pack, version)
        return {
            "pack": pack,
            "version": version,
            "sha": entry["sha"][:16],
            "status": entry["status"],
            "report": entry["report"],
            "simulation": entry.get("simulation"),
            "decision": entry.get("decision"),
            "elements": self.render_list(pack, entry, admin=True),
        }

    def render_list(self, pack: str, entry: dict[str, Any], *, admin: bool = False) -> list[dict[str, Any]]:
        """What the interface needs to draw a version's elements: their kind, settings and file addresses
        (the administrators' route in the sandbox, which serves versions not validated yet)."""
        base = f"/api/v1/{'admin/' if admin else ''}visuals/files/{pack}/{entry['sha'][:16]}"
        out = []
        for element in entry["report"]["elements"]:
            render = element["render"]
            folder = f"{base}/{element['folder']}"
            out.append(
                {
                    "pack": pack,
                    "sha": entry["sha"][:16],
                    "product": element["product"],
                    "type": element["type"],
                    "look": element.get("look"),
                    "kind": element["kind"],
                    "names": element["names"],
                    "file": f"{folder}/{render['file']}" if render.get("file") else None,
                    "css": [f"{folder}/{name}" for name in render.get("css") or []],
                    "stage": render.get("stage", False),
                    "shape": render.get("shape", 0),
                    "radius": render.get("radius"),
                    "reveal": render.get("reveal"),
                    "duration": render.get("duration"),
                    "palette": element.get("palette"),
                    "preview": f"{folder}/{element['preview']}" if element.get("preview") else None,
                    "nav": render.get("nav"),
                }
            )
        return out

    def active(self) -> dict[str, Any]:
        """What every member's interface loads: the elements of the published packs switched on."""
        elements = [e for pack, entry in self.live() for e in self.render_list(pack, entry)]
        stamp = ",".join(sorted(f"{pack}@{entry['sha'][:16]}" for pack, entry in self.live()))
        return {"elements": elements, "stamp": stamp}

    def served(self, pack: str, sha: str, name: str, *, manager: bool) -> Path | None:
        """A file of a version: any member's for the published packs switched on, a manager's for every
        version (the sandbox shows them before they are validated)."""
        holder = self.state["packs"].get(pack)
        if holder is None or len(sha) < 16:
            return None
        match = next((v for v in holder["versions"].values() if v["sha"].startswith(sha)), None)
        if match is None:
            return None
        current = holder["versions"].get(holder.get("current") or "")
        live = match is current and holder.get("enabled", True)
        if not (manager or live):
            return None
        return self.store.file(pack, match["sha"], name)
