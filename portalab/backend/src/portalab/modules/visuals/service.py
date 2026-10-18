"""The registry of visual packs and their life (spec 028).

A version goes through six steps — imported, analysed (its analysis and security findings), tested (what the
administrator's browser measured), reviewed (the economy decided per element, the confirmations), then
published, or refused. A published version is never changed in place: new content needs a new number. A pack
is enabled (its looks live), disabled (its products off sale, their owners keep them, its files no longer
served), archived (removed while members own its products: disabled, files kept) or removed for good (nobody
owned anything: files deleted, the rows kept for the audit trail). A version validated before can be rolled
back to, with the economy decided then.

The registry lives in the ``visuals`` schema, shared by every process; each change moves the registry's epoch
(and tells the members' interfaces through the live stream), and every process rebuilds what it keeps in
memory — the active manifest and the open vocabulary of looks — when it sees a newer epoch.

Publishing goes through ``marketplace.catalog_writer``: an element is a shop product like any other, owned,
equipped and refunded the usual way. Interfaces go through ``ui.interface_registry``.
"""

import asyncio
import gzip
import json
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.visuals import (
    CATALOG_WRITER,
    INTERFACE_REGISTRY,
    LOOK_TYPES,
    PACK_LOOKS,
    CatalogWriter,
    InterfaceRegistry,
    live_looks,
)
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, Unavailable, ValidationFailed
from portalab.core.live import publish_live
from portalab.core.time import Clock, utc_now
from portalab.modules.visuals.analysis import analyse, looks_of
from portalab.modules.visuals.github import GitHub, GitHubError, parse_address
from portalab.modules.visuals.manifest import (
    GIVEABLE,
    LOOK_FIELD,
    NOT_SOLD,
    ManifestError,
    parse_pack,
    version_key,
)
from portalab.modules.visuals.models import Element, LookClaim, Pack, PackVersion, RegistryEpoch, SceneBinding
from portalab.modules.visuals.store import Files, PackageError, Store, read_folder, read_source, read_zip
from portalab.modules.visuals.widgets import PackWidgets, pack_widget_key

SOCLE = "portalab-socle"
RESERVED_PREFIX = "portalab-"
ECONOMY_FIELDS = (
    "price", "rarity", "level", "supply", "collection", "icon", "season", "limit", "featured", "sold"
)  # fmt: skip
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
    "theme_pack": "packs",
    "booster": "boosters",
    "theme": "themes",
    "widget": "widgets",
    "widget_style": "widgets",
    "widget_option": "widgets",
}
PRODUCT_TYPES = {"theme_pack": "bundle", "widget_style": "widget_option", "widget_option": "widget_option"}
SKIN = "_skin"  # the widget frame's setting naming a pack's widget style
OPTIONS = "_options"  # the widget frame's setting listing the add-ons (packs' options) it wears


def widget_render(element: Mapping[str, Any]) -> dict[str, Any] | None:
    """What the interface needs of a widget, a widget style or a widget option besides its files."""
    payload = element.get("payload") or {}
    render = element.get("render") or {}
    if element["type"] == "widget":  # its sizes, pace, words when empty, its own settings
        return {k: v for k, v in payload.items() if k in ("sizes", "refresh_s", "empty", "options")}
    if element["type"] == "widget_style":  # the widget it is for (every widget: none)
        target = widget_target(payload.get("widget"))
        return {"for": target} if target != "*" else None
    if element["type"] == "widget_option":
        target = widget_target(payload.get("widget"))
        if "setting" in payload:  # a value of a pack widget's own setting
            return {"for": target, "setting": payload.get("setting"), "value": payload.get("value")}
        return {"for": None if target == "*" else target, "place": render.get("place")}
    return None


def widget_target(target: Any) -> str:
    """The dashboard key an element of a pack names: ``*`` (every widget), a widget's key, or this pack's own
    widget (its look, or ``pack.<look>``)."""
    if not isinstance(target, str) or not target or target == "*":
        return "*"
    return target if "." in target else pack_widget_key(target)


# the steps a version moves forward through (refused, superseded and purged end it)
ORDER = ("imported", "analysed", "tested", "reviewed", "published")
REFRESH_SECONDS = 2.0
BUNDLED = frozenset({".css", ".glsl", ".frag"})  # what a version's bundle holds (its scripts load apart)
BUNDLE_MAX = 8 * 1024 * 1024

Audit = Callable[[Principal | None, str, dict[str, Any]], Awaitable[None]]
Announce = Callable[[AsyncSession, str, dict[str, Any], Principal | None], Awaitable[None]]


class VisualPackError(ValidationFailed):
    default_code = "ui.visual_pack_invalid"
    default_title = "Invalid visual pack"


@dataclass(frozen=True, slots=True)
class Imported:
    pack: str
    version: str
    sha: str
    new: bool


def outcome_of(items: Iterable[Mapping[str, Any]], category: str) -> str:
    levels = {i["level"] for i in items if i.get("category", "analysis") == category}
    return "blocking" if "blocking" in levels else "warning" if "warning" in levels else "done"


def _later(step: str, than: str) -> str:
    """The furthest of two steps of the forward order."""
    return step if ORDER.index(step) >= ORDER.index(than) else than


# 028 (T038): Portalab's renderers an element of its own packs is drawn by with the element's parameters (an
# ambience's layers: flows, particles, a landscape) — sent like any pack's; the others (``builtin``, the
# navigations) are the interface's own code, nothing to load
SENT_RENDERERS = frozenset({"layers"})


class VisualPacks:
    def __init__(
        self,
        database: Database,
        root: Path,
        capabilities: CapabilityRegistry,
        *,
        github: GitHub | None = None,
        audit: Audit | None = None,
        announce: Announce | None = None,
        clock: Clock | None = None,
        widgets: PackWidgets | None = None,
    ) -> None:
        self.database = database
        self.widgets = widgets  # the live packs' widgets on this process's dashboard
        self.store = Store(root)
        self.capabilities = capabilities
        self.github = github or GitHub()
        self.audit = audit  # every action on a pack, in Portalab's audit log (sensitive)
        self.announce = announce  # the module's domain event (``visuals.pack.changed``)
        self.clock = clock
        self._manifest: dict[str, Any] = {"epoch": -1, "elements": [], "withheld": {}}
        self._reports: dict[tuple[str, str, str], float] = {}  # who reported what, when (an hour apart)
        self._live: dict[tuple[str, str], str] = {}  # (pack, fingerprint's first 16) → fingerprint, live ones
        self.withheld: dict[str, frozenset[str]] = {}  # Portalab's own looks whose pack is off, per type
        self._checked = 0.0
        self._refreshing = asyncio.Lock()
        self._bundles: dict[str, dict[str, str]] = {}  # a version's folder → its texts (immutable)
        self._live_files: tuple[int, bytes] | None = None  # every live file, gzipped, for one epoch

    # --- infrastructure ----------------------------------------------------------------------------------
    @staticmethod
    async def _lock(session: AsyncSession) -> None:
        """One registry write at a time, across every process."""
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('visuals.registry'))"))

    async def _bump(self, session: AsyncSession) -> int:
        epoch = (
            await session.execute(
                update(RegistryEpoch)
                .where(RegistryEpoch.id == 1)
                .values(epoch=RegistryEpoch.epoch + 1)
                .returning(RegistryEpoch.epoch)
            )
        ).scalar_one_or_none()
        if epoch is None:  # a registry created without its row
            session.add(RegistryEpoch(id=1, epoch=1))
            epoch = 1
        await publish_live(session, topic="visuals.changed", payload={"epoch": epoch}, clock=self.clock)
        self._checked = 0.0
        return int(epoch)

    def interfaces(self) -> InterfaceRegistry | None:
        providers = self.capabilities.system_providers(INTERFACE_REGISTRY)
        return providers[0].provider if providers else None

    def _writer(self) -> CatalogWriter:
        providers = self.capabilities.system_providers(CATALOG_WRITER)
        if not providers:
            raise Unavailable("The shop is not available.", code="ui.visual_pack_shop_unavailable")
        writer: CatalogWriter = providers[0].provider
        return writer

    async def _audited(self, actor: Principal | None, action: str, **context: Any) -> None:
        if self.audit is not None:
            await self.audit(actor, f"visuals.{action}", context)

    async def _announce(
        self, session: AsyncSession, action: str, actor: Principal | None, **context: Any
    ) -> None:
        if self.announce is not None:
            await self.announce(session, action, context, actor)

    @staticmethod
    async def _pack(session: AsyncSession, pack: str, *, lock: bool = False) -> Pack:
        query = select(Pack).where(Pack.id == pack)
        row = (await session.execute(query.with_for_update() if lock else query)).scalar_one_or_none()
        if row is None or row.state == "removed":
            raise NotFound("This visual pack is not known.", code="ui.visual_pack_not_found")
        return row

    @staticmethod
    async def _version(session: AsyncSession, pack: str, version: str) -> PackVersion:
        row = (
            await session.execute(
                select(PackVersion).where(PackVersion.pack_id == pack, PackVersion.version == version)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFound("This version is not known.", code="ui.visual_pack_not_found")
        return row

    @staticmethod
    async def _elements(session: AsyncSession, version_id: UUID) -> list[Element]:
        rows = await session.execute(
            select(Element).where(Element.version_id == version_id).order_by(Element.folder)
        )
        return list(rows.scalars())

    async def _taken(
        self, session: AsyncSession, except_pack: str
    ) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
        """The looks the live packs hold, and the products the other packs' current versions bring."""
        looks = {
            (row.type, row.look): row.pack_id
            for row in (
                await session.execute(select(LookClaim).where(LookClaim.pack_id != except_pack))
            ).scalars()
        }
        rows = await session.execute(
            select(Element.product_key, Pack.id)
            .join(PackVersion, PackVersion.id == Element.version_id)
            .join(Pack, Pack.current_version_id == PackVersion.id)
            .where(Pack.id != except_pack, Pack.state != "removed", Element.product_key.is_not(None))
        )
        products = {str(key): str(pack) for key, pack in rows.all()}
        return looks, products

    # --- import ------------------------------------------------------------------------------------------
    async def _import(
        self, session: AsyncSession, files: Files, source: dict[str, Any], *, builtin: bool = False
    ) -> Imported:
        raw = files.get("pack.json")
        if raw is None:
            raise VisualPackError("The pack has no pack.json.")
        try:
            manifest = parse_pack(raw)
        except ManifestError as error:
            raise VisualPackError(str(error)) from error
        if manifest.id.startswith(RESERVED_PREFIX) != builtin:
            raise Conflict(
                f"« {manifest.id} »: the ids starting with « {RESERVED_PREFIX} » are Portalab's own packs.",
                code="ui.visual_pack_reserved",
            )
        now = utc_now(self.clock)
        holder = (
            await session.execute(select(Pack).where(Pack.id == manifest.id).with_for_update())
        ).scalar_one_or_none()
        if holder is None:
            holder = Pack(
                id=manifest.id,
                builtin=builtin,
                socle=manifest.id == SOCLE,
                state="enabled" if manifest.id == SOCLE else "disabled",
                source=source,
                names=manifest.names.model_dump(),
                created_at=now,
                updated_at=now,
            )
            session.add(holder)
            await session.flush()
        elif holder.state == "removed":
            holder.state = "disabled"  # brought back: its old versions are gone
        holder.source = source
        holder.updated_at = now
        sha = files.sha
        known = (
            await session.execute(
                select(PackVersion).where(
                    PackVersion.pack_id == manifest.id, PackVersion.version == manifest.version
                )
            )
        ).scalar_one_or_none()
        retry = builtin and known is not None and not known.ever_published  # a built-in version that failed
        if known is not None and known.sha256 == sha and known.step != "purged" and not retry:
            return Imported(manifest.id, manifest.version, sha, False)
        if known is not None and known.ever_published:
            # a published version is never changed in place: the same number with other content is refused
            raise Conflict(
                f"Version {manifest.version} of « {manifest.id} » was published with other files: "
                "give the new content a new version number.",
                code="ui.visual_pack_version_taken",
            )
        folder = await asyncio.to_thread(self.store.keep, manifest.id, files)
        looks, products = await self._taken(session, manifest.id)
        report = await asyncio.to_thread(
            analyse,
            files,
            taken=looks,
            products_taken=products,
            interfaces=self.interfaces(),
            builtin=builtin,
        )
        outcomes = {
            "import": "done",
            "analysis": outcome_of(report["items"], "analysis"),
            "security": outcome_of(report["items"], "security"),
        }
        if known is None:
            known = PackVersion(pack_id=manifest.id, version=manifest.version, detected_at=now)
            session.add(known)
        else:  # a version never published, sent again with other files: analysed again from scratch
            await session.execute(delete(Element).where(Element.version_id == known.id))
            known.measures = known.draft = known.decision = None
        known.sha256 = sha
        known.folder = str(folder.relative_to(self.store.root))
        known.step = "analysed"
        known.outcomes = outcomes
        known.report = report
        known.detected_at = now
        await session.flush()
        for element in report["elements"]:
            if builtin:
                element["builtin"] = True  # its product, once it exists, is the administrators'
            session.add(
                Element(
                    version_id=known.id,
                    folder=element["folder"],
                    type=element["type"],
                    look=element.get("look"),
                    product_key=None
                    if element["type"] in NOT_SOLD or element.get("free")
                    else element["product"],
                    kind=element["kind"],
                    data=element,
                )
            )
        holder.names = manifest.names.model_dump()
        await session.flush()
        return Imported(manifest.id, manifest.version, sha, True)

    async def scan(self, actor: Principal | None = None) -> dict[str, Any]:
        """The inbox read again: every folder and zip there, new ones (or new versions) analysed."""
        found: list[dict[str, Any]] = []
        for path in self.store.sources():
            try:
                files = await asyncio.to_thread(read_source, path)
                async with self.database.unit_of_work() as uow:
                    await self._lock(uow.session)
                    imported = await self._import(uow.session, files, {"kind": "inbox", "path": path.name})
                found.append({"source": path.name, **_plain(imported)})
            except (PackageError, VisualPackError, Conflict) as error:
                found.append({"source": path.name, "error": str(error)})
        fresh = [f"{f['pack']}@{f['version']}" for f in found if f.get("new")]
        await self._audited(actor, "scanned", imported=fresh)
        return {"found": found}

    async def upload(self, filename: str, data: bytes, actor: Principal | None = None) -> Imported:
        """A zip sent from the administration: kept in the inbox (``uploads/``), then imported."""
        try:
            files = await asyncio.to_thread(read_zip, data)
        except PackageError as error:
            raise VisualPackError(str(error)) from error
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)[:80] or "pack.zip"
        async with self.database.unit_of_work() as uow:
            await self._lock(uow.session)
            imported = await self._import(uow.session, files, {"kind": "upload", "path": safe})
        uploads = self.store.inbox / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        (uploads / (safe if safe.endswith(".zip") else f"{safe}.zip")).write_bytes(data)
        await self._audited(actor, "uploaded", pack=imported.pack, version=imported.version, sha=imported.sha)
        return imported

    async def from_github(self, url: str, actor: Principal | None = None) -> Imported:
        """A pack on GitHub: the version it offers is downloaded, kept in the inbox and imported."""
        try:
            repository = parse_address(url)
            offer = await self.github.offer(repository)
            data = await self.github.download(repository, offer.ref)
            files = await asyncio.to_thread(read_zip, data, repository.folder)
        except (GitHubError, PackageError) as error:
            raise VisualPackError(str(error), code="ui.visual_pack_source") from error
        async with self.database.unit_of_work() as uow:
            await self._lock(uow.session)
            imported = await self._import(uow.session, files, {"kind": "github", "url": repository.url})
            holder = await self._pack(uow.session, imported.pack)
            holder.remote = {
                "version": offer.version,
                "ref": offer.ref,
                "release": offer.release,
                "checked_at": utc_now(self.clock).isoformat(timespec="seconds"),
            }
        downloads = self.store.inbox / "github"
        downloads.mkdir(parents=True, exist_ok=True)
        (downloads / f"{offer.pack}-{offer.version}.zip").write_bytes(data)
        await self._audited(
            actor, "downloaded", pack=imported.pack, version=imported.version, sha=imported.sha, url=url
        )
        return imported

    async def check_updates(self) -> list[dict[str, Any]]:
        """For each pack from GitHub: the version it offers now, and whether it is newer than ours —
        nothing is installed on its own."""
        async with self.database.session() as session:
            packs = list((await session.execute(select(Pack).where(Pack.state != "removed"))).scalars())
            numbers = {
                pack.id: [
                    v
                    for (v,) in (
                        await session.execute(
                            select(PackVersion.version).where(PackVersion.pack_id == pack.id)
                        )
                    ).all()
                ]
                for pack in packs
            }
        out: list[dict[str, Any]] = []
        offers: dict[str, dict[str, Any]] = {}
        for pack in packs:
            if (pack.source or {}).get("kind") != "github":
                continue
            try:
                offer = await self.github.offer(parse_address(pack.source["url"]))
            except (GitHubError, KeyError) as error:
                out.append({"pack": pack.id, "error": str(error)})
                continue
            offers[pack.id] = {
                "version": offer.version,
                "ref": offer.ref,
                "release": offer.release,
                "checked_at": utc_now(self.clock).isoformat(timespec="seconds"),
            }
            newest = max(numbers[pack.id], key=version_key, default=None)
            newer = newest is None or version_key(offer.version) > version_key(newest)
            out.append({"pack": pack.id, "offered": offer.version, "installed": newest, "update": newer})
        if offers:
            async with self.database.unit_of_work() as uow:
                for pack_id, remote in offers.items():
                    await uow.session.execute(update(Pack).where(Pack.id == pack_id).values(remote=remote))
        return out

    # --- the steps -----------------------------------------------------------------------------------------
    async def record_measures(
        self, actor: Principal, pack: str, version: str, results: list[dict[str, Any]]
    ) -> None:
        """What the Test step measured in the administrator's browser: compiled or not, frames per second,
        how long a script took to answer, errors."""
        async with self.database.unit_of_work() as uow:
            row = await self._version(uow.session, pack, version)
            if row.step in ("refused", "purged"):
                raise Conflict("This version is closed.", code="ui.visual_pack_closed")
            failing = any(
                r.get("errors") or r.get("compiled") is False or (r.get("fps") or 60) < 30 for r in results
            )
            row.measures = {
                "at": utc_now(self.clock).isoformat(timespec="seconds"),
                "by": str(actor.user_id) if actor.user_id else None,
                "results": results[:200],
            }
            row.outcomes = {**row.outcomes, "test": "warning" if failing else "done"}
            if row.step in ORDER and row.step != "published" and not _blocked(row):
                row.step = _later(row.step, "tested")
        await self._audited(actor, "tested", pack=pack, version=version, failing=failing)

    async def save_draft(
        self, actor: Principal, pack: str, version: str, draft: dict[str, Any]
    ) -> dict[str, Any]:
        """The Review step: the economy decided per element, the scene bindings, the confirmations."""
        async with self.database.unit_of_work() as uow:
            row = await self._version(uow.session, pack, version)
            if row.step in ("refused", "purged", "published"):
                raise Conflict("This version can no longer be reviewed.", code="ui.visual_pack_closed")
            row.draft = draft
            row.outcomes = {**row.outcomes, "review": "done"}
            if not _blocked(row):
                row.step = _later(row.step, "reviewed")
        return await self.detail(pack, version)

    async def refuse(
        self, actor: Principal | None, pack: str, version: str, reason: str | None = None
    ) -> None:
        async with self.database.unit_of_work() as uow:
            holder = await self._pack(uow.session, pack)
            row = await self._version(uow.session, pack, version)
            if holder.current_version_id == row.id:
                raise Conflict(
                    "This version is published: switch the pack off or roll it back instead.",
                    code="ui.visual_pack_published",
                )
            row.step = "refused"
            row.decision = {
                "by": str(actor.user_id) if actor and actor.user_id else None,
                "at": utc_now(self.clock).isoformat(timespec="seconds"),
                "reason": (reason or "")[:500],
            }
            await self._announce(uow.session, "refused", actor, pack=pack, version=version)
        await self._audited(actor, "refused", pack=pack, version=version, reason=(reason or "")[:500])

    # --- publication ----------------------------------------------------------------------------------------
    @staticmethod
    def product_of(element: Mapping[str, Any], decided: Mapping[str, Any]) -> dict[str, Any]:
        """The shop entry of an element: what it proposes, as the administrator decided."""
        economy = {**element["economy"], **{k: v for k, v in decided.items() if k in ECONOMY_FIELDS}}
        payload = dict(element.get("payload") or {})
        # 030: a plugin's kind of visual names its look ``look`` (the plugin's product type reads it)
        field = LOOK_FIELD.get(element["type"]) or (
            "look" if str(element["type"]).startswith("plugin:") else None
        )
        if field and element.get("look"):
            payload[field] = element["look"]
        if element["type"] == "widget_style":
            # a frame's look worn by any widget (``*``) or the one it names: ``_skin`` (a frame setting)
            payload = {"option": f"{widget_target(payload.get('widget'))}:{SKIN}={element.get('look')}"}
        if element["type"] == "widget":
            payload = {"widget": pack_widget_key(str(element.get("look")))}
        if element["type"] == "widget_option":
            option = element.get("payload") or {}
            target = widget_target(option.get("widget"))
            if (
                "setting" in option
            ):  # a value of a pack widget's own setting: ``pack.<widget>:<setting>=<value>``
                payload = {"option": f"{target}:{option.get('setting')}={option.get('value')}"}
            else:  # an add-on a widget wears (``_options``, the frame's list of them)
                payload = {"option": f"{target}:{OPTIONS}={element.get('look')}"}
        return {
            "key": element["product"],
            "type": PRODUCT_TYPES.get(element["type"], element["type"]),
            "price": economy.get("price"),
            "rarity": economy.get("rarity") or "common",
            "names": {k: v for k, v in element["names"].items() if v},
            "descriptions": {k: v for k, v in element["descriptions"].items() if v},
            "payload": payload,
            "collection": economy.get("collection") or DEFAULT_COLLECTIONS.get(element["type"], "looks"),
            "icon": economy.get("icon"),
            "featured": bool(economy.get("featured")),
            "level": economy.get("level"),
            "supply": economy.get("supply"),
            "limit": tuple(economy["limit"]) if economy.get("limit") else None,
            "repeatable": bool(economy.get("repeatable")),
            "reward_only": bool(economy.get("reward_only"))
            or (economy.get("price") is None and element["type"] not in ("bundle", "theme_pack")),
            "season": economy.get("season"),
            **({"contribution": economy["contribution"]} if economy.get("contribution") else {}),
            # 028: Portalab's own products, once they exist, are the administrators' (never revised)
            **({"keep_existing": True} if element.get("builtin") else {}),
        }

    async def _interface(
        self, actor: Principal, pack: str, version: PackVersion, element: Mapping[str, Any], *, enabled: bool
    ) -> None:
        """An interface (element ``theme``) in UI's registry: registered, or its definition updated (only one
        this pack brought), switched on or off with its pack."""
        if element["type"] != "theme":
            return
        interfaces = self.interfaces()
        if interfaces is None:
            raise Unavailable("Interfaces are not available.", code="ui.visual_pack_interfaces_unavailable")
        if element.get("builtin") and element["kind"] == "renderer":
            # one of Portalab's own interfaces (UI registers it): only switched on and off with its pack
            # (never the fallbacks: the socle is always on)
            await interfaces.set_enabled(actor, element["look"], enabled)
            return
        if not enabled:
            if await interfaces.source_of(element["look"]) == f"visuals:{pack}":
                await interfaces.set_enabled(actor, element["look"], False)
            return
        path = self.store.file(pack, version.sha256, f"{element['folder']}/{element['render']['file']}")
        if path is None:
            raise VisualPackError("The interface's definition is missing.")
        document = json.loads(path.read_text(encoding="utf-8"))
        token = PACK_LOOKS.set(frozenset(looks_of(version.report)))
        try:
            await interfaces.put(actor, document, source=f"visuals:{pack}")
            await interfaces.set_enabled(actor, element["look"], True)
        finally:
            PACK_LOOKS.reset(token)

    async def _release(self, session: AsyncSession, pack: str) -> None:
        """The looks this pack holds released — and the ones it had taken over given back to their holder,
        when that one is still live and still has them."""
        claims = list((await session.execute(select(LookClaim).where(LookClaim.pack_id == pack))).scalars())
        await session.execute(delete(LookClaim).where(LookClaim.pack_id == pack))
        for claim in claims:
            if not claim.replaced_from:
                continue
            row = (
                await session.execute(
                    select(Element.id)
                    .join(PackVersion, PackVersion.id == Element.version_id)
                    .join(Pack, Pack.current_version_id == PackVersion.id)
                    .where(
                        Pack.id == claim.replaced_from,
                        Pack.state == "enabled",
                        Element.type == claim.type,
                        Element.look == claim.look,
                    )
                )
            ).first()
            if row is not None:
                session.add(
                    LookClaim(
                        type=claim.type, look=claim.look, pack_id=claim.replaced_from, element_id=row[0]
                    )
                )
        await session.flush()

    async def _claim(
        self, session: AsyncSession, pack: str, elements: list[Element], replaces: set[str], *, trusted: bool
    ) -> None:
        """The looks of a version going live claimed — a look another live pack holds is refused, unless the
        administrator decided this element replaces it."""
        for element in elements:
            if not element.look:
                continue
            held = await session.get(LookClaim, (element.type, element.look))
            if held is not None and held.pack_id == pack:
                await session.delete(held)
                await session.flush()
                held = None
            if held is not None:
                if not (trusted or f"{element.type}:{element.look}" in replaces) or not element.data.get(
                    "replaces"
                ):
                    raise Conflict(
                        f"« {element.look} » ({element.type}) is held by the pack « {held.pack_id} ».",
                        code="ui.visual_pack_claimed",
                    )
                previous = held.pack_id
                await session.delete(held)
                await session.flush()
                session.add(
                    LookClaim(
                        type=element.type,
                        look=element.look,
                        pack_id=pack,
                        element_id=element.id,
                        replaced_from=previous,
                    )
                )
            else:
                session.add(
                    LookClaim(type=element.type, look=element.look, pack_id=pack, element_id=element.id)
                )
        await session.flush()

    async def _go_live(
        self,
        session: AsyncSession,
        actor: Principal,
        holder: Pack,
        version: PackVersion,
        economy: Mapping[str, Mapping[str, Any]],
        *,
        replaces: set[str] | frozenset[str] = frozenset(),
        trusted: bool = False,
        previous: PackVersion | None = None,
    ) -> dict[str, str]:
        elements = await self._elements(session, version.id)
        await self._release(session, holder.id)
        await self._claim(session, holder.id, elements, set(replaces), trusted=trusted)
        writer = self._writer()
        outcomes: dict[str, str] = {}
        # what switching the pack off took off sale goes back on sale — and only that: a product of Portalab's
        # own catalog the administrators had taken off sale stays off
        withdrawn = set((version.decision or {}).get("withdrawn") or [])
        for element in elements:
            await self._interface(actor, holder.id, version, element.data, enabled=True)
            if element.product_key is None:
                continue
            decided = economy.get(element.product_key, {})
            if element.type in GIVEABLE and not {**element.data["economy"], **decided}.get("sold", True):
                # given to everyone: no product — one sold before goes off sale (its owners keep it)
                if element.product_key in await writer.existing([element.product_key]):
                    await writer.withdraw(actor, element.product_key)
                outcomes[element.product_key] = "given"
                continue
            product = self.product_of(element.data, decided)
            if holder.builtin:
                product["resume"] = element.product_key in withdrawn
            outcomes[element.product_key] = await writer.publish(actor, product)
        if withdrawn:
            version.decision = {**(version.decision or {}), "withdrawn": []}
        if previous is not None and previous.id != version.id:
            for element in await self._elements(session, previous.id):
                if element.product_key and element.product_key not in outcomes:
                    await writer.withdraw(actor, element.product_key)  # its owners keep it
                if element.type == "theme" and element.look not in {
                    e.look for e in elements if e.type == "theme"
                }:
                    await self._interface(actor, holder.id, previous, element.data, enabled=False)
        return outcomes

    async def _go_dark(
        self, session: AsyncSession, actor: Principal, holder: Pack, version: PackVersion
    ) -> None:
        await self._release(session, holder.id)
        writer = self._writer()
        withdrawn: list[str] = []
        for element in await self._elements(session, version.id):
            await self._interface(actor, holder.id, version, element.data, enabled=False)
            if element.product_key is not None and await writer.withdraw(actor, element.product_key):
                withdrawn.append(element.product_key)  # on sale until now: back on sale when switched on
        previous = set((version.decision or {}).get("withdrawn") or [])
        version.decision = {**(version.decision or {}), "withdrawn": sorted(previous | set(withdrawn))}

    @staticmethod
    def _missing_confirmations(
        version: PackVersion, elements: list[Element], confirmations: Mapping[str, Any]
    ) -> list[str]:
        missing: list[str] = []
        if version.report.get("summary", {}).get("script") and not confirmations.get("scripts"):
            missing.append("scripts")
        accepted = set(confirmations.get("contracts") or [])
        for element in elements:
            for contract in element.data.get("contracts") or []:
                if contract not in accepted:
                    missing.append(f"contract:{contract}")
        return missing

    async def publish(
        self,
        actor: Principal,
        pack: str,
        version: str,
        economy: Mapping[str, Mapping[str, Any]] | None = None,
        confirmations: Mapping[str, Any] | None = None,
        *,
        trusted: bool = False,
    ) -> dict[str, Any]:
        """Validates a version: its elements published in the shop with the economy decided (each element's
        proposal where nothing was changed), the version becomes the pack's current one, switched on.
        ``trusted``: a built-in pack shipped with Portalab, or a rollback (its decision was made before)."""
        confirmations = dict(confirmations or {})
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await self._lock(session)
            holder = await self._pack(session, pack, lock=True)
            row = await self._version(session, pack, version)
            if row.step in ("refused", "purged"):
                raise Conflict("This version is closed.", code="ui.visual_pack_closed")
            if not row.report.get("summary", {}).get("publishable"):
                raise VisualPackError("This version has blocking problems.", code="ui.visual_pack_blocked")
            elements = await self._elements(session, row.id)
            if not trusted:
                missing = self._missing_confirmations(row, elements, confirmations)
                if missing:
                    raise VisualPackError(
                        f"Confirm explicitly: {', '.join(missing)}.", code="ui.visual_pack_confirm"
                    )
            draft = row.draft or {}
            decided: dict[str, dict[str, Any]] = {
                key: dict(value) for key, value in ((row.decision or {}).get("economy") or {}).items()
            }
            for key, value in {**(draft.get("economy") or {}), **(economy or {})}.items():
                decided[key] = {
                    **decided.get(key, {}),
                    **{k: v for k, v in value.items() if k in ECONOMY_FIELDS},
                }
            previous = (
                await session.get(PackVersion, holder.current_version_id)
                if holder.current_version_id
                else None
            )
            replaces = set(confirmations.get("replaces") or [])
            # a built-in pack updated by a release keeps the administrator's choice (on or off)
            enable = holder.state == "enabled" or not (holder.builtin and trusted)
            products: dict[str, str] = {}
            if enable:
                products = await self._go_live(
                    session,
                    actor,
                    holder,
                    row,
                    decided,
                    replaces=replaces,
                    trusted=trusted,
                    previous=previous,
                )
            if previous is not None and previous.id != row.id:
                previous.step = "superseded"
            row.step = "published"
            row.ever_published = True
            row.published_at = utc_now(self.clock)
            row.outcomes = {**row.outcomes, "validation": "done"}
            row.decision = {
                "by": str(actor.user_id) if actor.user_id else None,
                "at": utc_now(self.clock).isoformat(timespec="seconds"),
                "economy": decided,
                "confirmations": {
                    "scripts": bool(row.report.get("summary", {}).get("script")),
                    "replaces": sorted(replaces),
                    "contracts": sorted(confirmations.get("contracts") or []),
                },
                "trusted": trusted,
            }
            holder.current_version_id = row.id
            if enable:
                holder.state = "enabled"
            for look, booster in ((row.draft or {}).get("bindings") or {}).items():
                if booster:  # the scenes the Review step bound (a booster's key, or ``*`` for all)
                    await session.flush()
                    await self.bind_scene(actor, str(booster), (pack, str(look)), session=session)
            holder.updated_at = utc_now(self.clock)
            await self._bump(session)
            await self._announce(session, "published", actor, pack=pack, version=version)
        await self._audited(
            actor,
            "published",
            pack=pack,
            version=version,
            sha=row.sha256,
            script=bool(row.report.get("summary", {}).get("script")),
            economy=decided,
            trusted=trusted,
        )
        return {"pack": pack, "version": version, "products": products}

    # --- booster scenes ---------------------------------------------------------------------------------
    async def bind_scene(
        self,
        actor: Principal,
        booster_key: str,
        scene: tuple[str, str] | None,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """The scene a booster opens with (``*``: every booster without one of its own); ``None`` unbinds."""

        async def work(db: AsyncSession) -> None:
            await db.execute(delete(SceneBinding).where(SceneBinding.booster_key == booster_key))
            if scene is None:
                return
            pack, look = scene
            element_id = (
                await db.execute(
                    select(Element.id)
                    .join(PackVersion, PackVersion.id == Element.version_id)
                    .join(Pack, Pack.current_version_id == PackVersion.id)
                    .where(Pack.id == pack, Element.type == "booster_scene", Element.look == look)
                )
            ).scalar_one_or_none()
            if element_id is None:
                raise NotFound("This scene is not published.", code="ui.visual_scene_not_found")
            db.add(
                SceneBinding(
                    booster_key=booster_key,
                    element_id=element_id,
                    bound_by=actor.user_id,
                    bound_at=utc_now(self.clock),
                )
            )
            await self._bump(db)

        if session is not None:
            await work(session)
        else:
            async with self.database.unit_of_work() as uow:
                await work(uow.session)
        await self._audited(
            actor, "scene_bound", booster=booster_key, scene=":".join(scene) if scene else None
        )

    async def scene_for(self, booster_key: str) -> dict[str, Any] | None:
        """The scene a booster opens with — its own, else the default one bound to every booster, else none
        (Portalab's own scene). Only a live pack's scene counts; its parts are drawn by their own kind."""
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(SceneBinding.booster_key, Pack.id, PackVersion, Element)
                    .join(Element, Element.id == SceneBinding.element_id)
                    .join(PackVersion, PackVersion.id == Element.version_id)
                    .join(Pack, Pack.current_version_id == PackVersion.id)
                    .where(SceneBinding.booster_key.in_((booster_key, "*")), Pack.state == "enabled")
                )
            ).all()
            if not rows:
                return None
            _, pack_id, version, scene = sorted(rows, key=lambda r: r[0] == "*")[0]
            by_folder = {
                e.folder.removeprefix("elements/"): e for e in await self._elements(session, version.id)
            }

        def part(folder: Any) -> dict[str, Any] | None:
            element = by_folder.get(str(folder).removeprefix("elements/"))
            return self.render_list(pack_id, version, [element.data])[0] if element else None

        parts: dict[str, Any] = {}
        for slot, value in ((scene.data.get("payload") or {}).get("parts") or {}).items():
            if isinstance(value, dict):
                parts[slot] = {rarity: part(folder) for rarity, folder in value.items() if part(folder)}
            elif part(value):
                parts[slot] = part(value)
        return {"pack": pack_id, "look": scene.look, "names": scene.data.get("names"), "parts": parts}

    # --- the pack's life ------------------------------------------------------------------------------------
    async def set_state(self, actor: Principal, pack: str, enabled: bool) -> None:
        """Off: its products leave the shop (owners keep them), its files are no longer served, its looks
        fall back to the defaults. On: back, with the economy decided (an archived pack comes back so)."""
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await self._lock(session)
            holder = await self._pack(session, pack, lock=True)
            if holder.socle and not enabled:
                raise Conflict("Portalab's socle is always on.", code="ui.visual_pack_socle")
            if holder.current_version_id is None:
                raise Conflict("This pack has no published version.", code="ui.visual_pack_unpublished")
            version = await session.get(PackVersion, holder.current_version_id)
            assert version is not None
            if enabled:
                await self._go_live(
                    session,
                    actor,
                    holder,
                    version,
                    (version.decision or {}).get("economy") or {},
                    trusted=True,
                )
            else:
                await self._go_dark(session, actor, holder, version)
            holder.state = "enabled" if enabled else "disabled"
            holder.updated_at = utc_now(self.clock)
            await self._bump(session)
            await self._announce(
                session,
                "switched_on" if enabled else "switched_off",
                actor,
                pack=pack,
                version=version.version,
            )
        await self._audited(
            actor, "switched_on" if enabled else "switched_off", pack=pack, version=version.version
        )

    async def set_builtin_state(self, actor: Principal, enabled: bool) -> list[str]:
        """Every one of Portalab's own packs switched on (the whole catalog) or off (the socle stays on);
        returns the packs changed."""
        async with self.database.session() as session:
            packs = [
                p.id
                for p in (
                    await session.execute(
                        select(Pack).where(
                            Pack.builtin,
                            Pack.socle.is_(False),
                            Pack.current_version_id.is_not(None),
                            Pack.state.in_(("disabled", "archived") if enabled else ("enabled",)),
                        )
                    )
                ).scalars()
            ]
        for pack in packs:
            await self.set_state(actor, pack, enabled)
        return packs

    async def rollback(self, actor: Principal, pack: str, version: str) -> dict[str, Any]:
        """Back to a version validated before, with the economy decided then."""
        async with self.database.session() as session:
            row = await self._version(session, pack, version)
            if not row.ever_published:
                raise Conflict(
                    "Only a version validated before can be rolled back to.", code="ui.visual_pack_rollback"
                )
            replaces = ((row.decision or {}).get("confirmations") or {}).get("replaces") or []
        result = await self.publish(actor, pack, version, {}, {"replaces": replaces}, trusted=True)
        await self._audited(actor, "rolled_back", pack=pack, version=version)
        return result

    async def owners(self, pack: str) -> int:
        """How many live ownerships the products of every version of this pack have."""
        async with self.database.session() as session:
            keys = {
                key
                for (key,) in (
                    await session.execute(
                        select(Element.product_key)
                        .join(PackVersion, PackVersion.id == Element.version_id)
                        .where(
                            PackVersion.pack_id == pack,
                            PackVersion.ever_published,
                            Element.product_key.is_not(None),
                        )
                    )
                ).all()
            }
        return await self._writer().owners(sorted(keys)) if keys else 0

    async def remove(self, actor: Principal, pack: str) -> dict[str, Any]:
        """Removing a pack some member owns a product of archives it (switched off, its files and versions
        kept); a pack nobody owns anything of is removed for good (files deleted, products retired)."""
        owners = await self.owners(pack)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await self._lock(session)
            holder = await self._pack(session, pack, lock=True)
            if holder.socle:
                raise Conflict("Portalab's socle is always on.", code="ui.visual_pack_socle")
            current = (
                await session.get(PackVersion, holder.current_version_id)
                if holder.current_version_id
                else None
            )
            if current is not None and holder.state == "enabled":
                await self._go_dark(session, actor, holder, current)
            if owners:
                holder.state = "archived"
                outcome = "archived"
            else:
                writer = self._writer()
                versions = list(
                    (await session.execute(select(PackVersion).where(PackVersion.pack_id == pack))).scalars()
                )
                for version in versions:
                    for element in await self._elements(session, version.id):
                        if element.product_key and version.ever_published:
                            await writer.retire(actor, element.product_key)
                    version.step = "purged"
                holder.state = "removed"
                holder.current_version_id = None
                outcome = "removed"
            holder.updated_at = utc_now(self.clock)
            await self._bump(session)
            await self._announce(session, outcome, actor, pack=pack, owners=owners)
        if outcome == "removed":
            await asyncio.to_thread(self.store.drop, pack)
        await self._audited(actor, outcome, pack=pack, owners=owners)
        return {"outcome": outcome, "owners": owners}

    async def purge(self, actor: Principal, pack: str, version: str) -> None:
        """A version never published: its files deleted (the row stays, for the audit trail)."""
        async with self.database.unit_of_work() as uow:
            row = await self._version(uow.session, pack, version)
            if row.ever_published:
                raise Conflict(
                    "A version published once is kept (it can be rolled back to).",
                    code="ui.visual_pack_published",
                )
            shared = (
                await uow.session.execute(
                    select(PackVersion.id).where(
                        PackVersion.pack_id == pack,
                        PackVersion.sha256 == row.sha256,
                        PackVersion.id != row.id,
                        PackVersion.step != "purged",
                    )
                )
            ).first()
            row.step = "purged"
            sha = row.sha256
            await self._announce(uow.session, "purged", actor, pack=pack, version=version)
        if shared is None:
            await asyncio.to_thread(self.store.drop, pack, sha)
        await self._audited(actor, "purged", pack=pack, version=version)

    # --- reading --------------------------------------------------------------------------------------------
    async def listing(self) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            packs = list(
                (
                    await session.execute(select(Pack).where(Pack.state != "removed").order_by(Pack.id))
                ).scalars()
            )
            versions = list((await session.execute(select(PackVersion))).scalars())
            failures = {
                version_id: int(count or 0)
                for version_id, count in (
                    await session.execute(
                        text(
                            "SELECT version_id, sum((data->>'failures')::int) FROM visuals.elements "
                            "WHERE data ? 'failures' GROUP BY version_id"
                        )
                    )
                ).all()
            }
        by_pack: dict[str, list[PackVersion]] = {}
        for version in versions:
            by_pack.setdefault(version.pack_id, []).append(version)
        out = []
        for pack in packs:
            mine = sorted(by_pack.get(pack.id, []), key=lambda v: version_key(v.version), reverse=True)
            current = next((v for v in mine if v.id == pack.current_version_id), None)
            out.append(
                {
                    "id": pack.id,
                    "names": pack.names,
                    "builtin": pack.builtin,
                    "socle": pack.socle,
                    "source": pack.source,
                    "state": pack.state,
                    "current": current.version if current else None,
                    "remote": pack.remote,
                    "update": bool(
                        pack.remote
                        and (not mine or version_key(pack.remote["version"]) > version_key(mine[0].version))
                    ),
                    "versions": [_version_row(v) for v in mine if v.step != "purged"],
                    "failures": failures.get(pack.current_version_id, 0) if pack.current_version_id else 0,
                    # 028: what it brings for the dashboard (its live version's, else its latest's)
                    "widgets": _widget_elements(current or (mine[0] if mine else None)),
                }
            )
        return out

    async def detail(self, pack: str, version: str) -> dict[str, Any]:
        async with self.database.session() as session:
            holder = await self._pack(session, pack)
            row = await self._version(session, pack, version)
            elements = await self._elements(session, row.id)
        return {
            **_version_row(row),
            "pack": pack,
            "builtin": holder.builtin,
            "current": holder.current_version_id == row.id,
            "report": row.report,
            "measures": row.measures,
            "draft": row.draft,
            "changes": row.changes,
            "elements": self.render_list(pack, row, [e.data for e in elements], admin=True),
        }

    @staticmethod
    def render_list(
        pack: str, version: PackVersion, elements: Iterable[Mapping[str, Any]], *, admin: bool = False
    ) -> list[dict[str, Any]]:
        """What the interface needs to draw a version's elements: their kind, settings and file addresses
        (the administrators' route serves versions not validated yet)."""
        base = f"/api/v1/{'admin/' if admin else ''}visuals/files/{pack}/{version.sha256[:16]}"
        out = []
        for element in elements:
            render = element["render"]
            folder = f"{base}/{element['folder']}"
            entry = {
                "pack": pack,
                "sha": version.sha256[:16],
                "product": None if element["type"] in NOT_SOLD else element["product"],
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
                "start": render.get("start"),
                "cycle": render.get("cycle") or None,
                "palette": element.get("palette"),
                "preview": f"{folder}/{element['preview']}" if element.get("preview") else None,
                "nav": render.get("nav"),
                "renderer": render.get("renderer"),
                "params": render.get("params") or None,
                "rarity": render.get("rarity"),
                "parts": (element.get("payload") or {}).get("parts"),
                "contracts": element.get("contracts") or None,
                # a widget: the sizes it takes and what it shows when it has nothing (its data: contracts)
                "widget": widget_render(element),
            }
            out.append(
                {k: v for k, v in entry.items() if v not in (None, [], {})} | {"names": element["names"]}
            )
        return out

    async def report_failure(self, actor: Principal, pack: str, sha: str, element: str, reason: str) -> bool:
        """A live element failed in a member's page (a script that did not answer, or broke): counted on the
        element, for the administrators — at most once an hour per member and element."""
        await self.refresh()
        full = self._live.get((pack, sha.lower()[:16]))
        if full is None:
            return False
        key = (str(actor.user_id), pack, element)
        now = time.monotonic()
        if now - self._reports.get(key, -3600.0) < 3600:
            return False
        self._reports[key] = now
        if len(self._reports) > 10_000:
            self._reports = {k: v for k, v in self._reports.items() if now - v < 3600}
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(
                text(
                    "UPDATE visuals.elements e SET data = jsonb_set(e.data, '{failures}', "
                    "to_jsonb(coalesce((e.data->>'failures')::int, 0) + 1)) "
                    "FROM visuals.pack_versions v WHERE v.id = e.version_id AND v.pack_id = :pack "
                    "AND v.sha256 = :sha AND (e.product_key = :element OR e.data->>'product' = :element)"
                ),
                {"pack": pack, "sha": full, "element": element[:64]},
            )
            if not result.rowcount:  # type: ignore[attr-defined]
                return False
            await self._announce(
                uow.session, "element_failed", actor, pack=pack, element=element[:64], reason=reason[:20]
            )
        return True

    async def epoch(self) -> int:
        async with self.database.session() as session:
            value = (await session.execute(select(RegistryEpoch.epoch).where(RegistryEpoch.id == 1))).scalar()
        return int(value or 0)

    async def refresh(self, *, force: bool = False) -> None:
        """Rebuilds the active manifest and the open vocabulary when the registry's epoch moved (checked at
        most every few seconds)."""
        if not force and time.monotonic() - self._checked < REFRESH_SECONDS:
            return
        async with self._refreshing:
            if not force and time.monotonic() - self._checked < REFRESH_SECONDS:
                return
            epoch = await self.epoch()
            self._checked = time.monotonic()
            if epoch == self._manifest["epoch"] and not force:
                return
            async with self.database.session() as session:
                rows = (
                    await session.execute(
                        select(Pack.id, PackVersion, Element)
                        .join(PackVersion, PackVersion.id == Pack.current_version_id)
                        .join(Element, Element.version_id == PackVersion.id)
                        .where(Pack.state == "enabled")
                        .order_by(Pack.id, Element.folder)
                    )
                ).all()
                claims = list((await session.execute(select(LookClaim))).scalars())
                # the looks whose pack is off (Portalab's or imported): their wearers see the default instead,
                # their owners see them « currently unavailable »
                withheld_rows = (
                    await session.execute(
                        select(Element.type, Element.look)
                        .join(PackVersion, PackVersion.id == Element.version_id)
                        .join(Pack, Pack.current_version_id == PackVersion.id)
                        .where(Pack.state != "enabled", Element.look.is_not(None))
                    )
                ).all()
            elements: list[dict[str, Any]] = []
            for pack_id, version, element in rows:
                if (
                    element.data.get("builtin")
                    and element.kind == "renderer"
                    and (element.data.get("render") or {}).get("renderer") not in SENT_RENDERERS
                ):
                    continue  # drawn by the interface's own code: nothing to load
                elements.extend(self.render_list(pack_id, version, [element.data]))
            by_type: dict[str, list[str]] = {}
            for claim in claims:
                by_type.setdefault(claim.type, []).append(claim.look)
            live = {(claim.type, claim.look) for claim in claims}
            withheld: dict[str, list[str]] = {}
            for kind, look in withheld_rows:
                if (kind, look) not in live:
                    withheld.setdefault(str(kind), []).append(str(look))
            live_looks.replace(by_type, epoch, held=withheld)
            if self.widgets is not None:
                self.widgets.sync(
                    {
                        "pack": pack_id,
                        "sha": version.sha256[:16],
                        "look": element.look,
                        "contracts": element.data.get("contracts") or [],
                        "payload": element.data.get("payload") or {},
                        "economy": element.data.get("economy") or {},
                    }
                    for pack_id, version, element in rows
                    if element.type == "widget"
                )
            self.withheld = {kind: frozenset(looks) for kind, looks in withheld.items()}
            self._live = {(pack_id, version.sha256[:16]): version.sha256 for pack_id, version, _ in rows}
            self._manifest = {
                "epoch": epoch,
                "elements": elements,
                "withheld": {kind: sorted(looks) for kind, looks in withheld.items()},
            }

    async def active(self) -> dict[str, Any]:
        """What every member's interface loads: the elements of the live packs (cached per epoch)."""
        await self.refresh()
        return self._manifest

    async def looks(self) -> dict[str, Any]:
        """028: the looks one may name, per type — Portalab's own packs', then the live packs'; the socle's
        (free for everyone); those whose pack is off. None is written in the interface's code: its pickers
        and the shop's editor read them here."""
        await self.refresh()
        return {
            "epoch": live_looks.epoch,
            "looks": {kind: list(live_looks.known(kind)) for kind in LOOK_TYPES},
            "free": {kind: sorted(live_looks.free(kind)) for kind in LOOK_TYPES if live_looks.free(kind)},
            "held": {kind: sorted(live_looks.held(kind)) for kind in LOOK_TYPES if live_looks.held(kind)},
        }

    async def served(self, pack: str, sha: str, name: str, *, manager: bool) -> Path | None:
        """A file of a version: any member's for the live packs' current versions, a manager's for every
        version not purged (the Test step shows them before they are validated)."""
        if len(sha) < 16 or not sha.isalnum():
            return None
        if not manager:  # a member's: the live versions this process keeps in memory (no query per file)
            await self.refresh()
            full = self._live.get((pack, sha.lower()[:16]))
            return self.store.file(pack, full, name) if full and full.startswith(sha.lower()) else None
        async with self.database.session() as session:
            row = (
                await session.execute(
                    select(Pack, PackVersion)
                    .join(PackVersion, PackVersion.pack_id == Pack.id)
                    .where(
                        Pack.id == pack,
                        PackVersion.sha256.startswith(sha.lower()),
                        PackVersion.step != "purged",
                    )
                )
            ).first()
        if row is None:
            return None
        holder, version = row
        live = holder.state == "enabled" and holder.current_version_id == version.id
        if not (manager or live):
            return None
        return self.store.file(pack, version.sha256, name)

    async def bundle(self, pack: str, sha: str, *, manager: bool) -> dict[str, str] | None:
        """A version's stylesheets and shaders in one answer (028 B2: Portalab's own packs hold hundreds of
        looks — one request per pack version rather than one per file); the same rights as ``served``."""
        manifest = await self.served(pack, sha, "pack.json", manager=manager)
        if manifest is None:
            return None
        folder = manifest.parent
        cached = self._bundles.get(str(folder))
        if cached is not None:
            return cached
        out: dict[str, str] = {}
        size = 0
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() not in BUNDLED or not path.is_file():
                continue
            text_ = path.read_text(encoding="utf-8", errors="replace")
            size += len(text_)
            if size > BUNDLE_MAX:
                break  # the rest is fetched file by file
            out[path.relative_to(folder).as_posix()] = text_
        if len(self._bundles) > 256:
            self._bundles.clear()
        self._bundles[str(folder)] = out
        return out

    async def live_files(self) -> tuple[int, bytes]:
        """028 (B2): every stylesheet and shader the live packs' elements use, in one gzip answer keyed by
        their addresses — a page loads all the looks in one request rather than one per pack (a browser
        caches nothing from an origin whose certificate it does not trust: the LAN's). Cached per epoch."""
        await self.refresh()
        epoch = int(self._manifest.get("epoch", -1))
        if self._live_files is not None and self._live_files[0] == epoch:
            return self._live_files
        files: dict[str, str] = {}
        prefix = "/api/v1/visuals/files/"
        for element in self._manifest.get("elements", []):
            for address in [*(element.get("css") or []), element.get("file")]:
                if not address or not address.startswith(prefix) or address in files:
                    continue
                pack, sha, name = address[len(prefix) :].split("/", 2)
                found = await self.bundle(pack, sha, manager=False)
                if found is not None and name in found:
                    files[address] = found[name]
                elif name.endswith(".json"):  # an interface's definition
                    path = await self.served(pack, sha, name, manager=False)
                    if path is not None:
                        files[address] = path.read_text(encoding="utf-8", errors="replace")
        body = gzip.compress(json.dumps({"epoch": epoch, "files": files}, ensure_ascii=False).encode(), 6)
        self._live_files = (epoch, body)
        return self._live_files

    # --- the proof of concept's registry --------------------------------------------------------------------
    async def import_poc_state(self, actor: Principal) -> int:
        """The proof of concept kept its registry in ``state.json``: its versions are imported once (from
        their stored folders), the published ones published again with the economy decided then, then the
        file is renamed. Returns how many versions came in."""
        path = self.store.state_file
        if not path.is_file():
            return 0
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 0
        count = 0
        for pack, entry in (state.get("packs") or {}).items():
            for number, version in sorted(
                (entry.get("versions") or {}).items(), key=lambda kv: version_key(kv[0])
            ):
                folder = self.store.root / str(version.get("folder", ""))
                if not folder.is_dir():
                    continue
                try:
                    files = await asyncio.to_thread(read_folder, folder)
                    async with self.database.unit_of_work() as uow:
                        await self._lock(uow.session)
                        await self._import(uow.session, files, entry.get("source") or {"kind": "inbox"})
                    count += 1
                    if version.get("status") == "approved" and entry.get("current") == number:
                        economy = (version.get("decision") or {}).get("economy") or {}
                        await self.publish(actor, pack, number, economy, trusted=True)
                        if not entry.get("enabled", True):
                            await self.set_state(actor, pack, False)
                except (PackageError, VisualPackError, Conflict, NotFound, Unavailable):
                    continue
        path.rename(path.with_suffix(".json.migrated"))
        return count


def _widget_elements(version: PackVersion | None) -> list[dict[str, Any]]:
    """A version's widgets, widget looks and widget options, as the Extensions → Widgets tab lists them."""
    if version is None:
        return []
    decided = (version.decision or {}).get("economy") or (version.draft or {}).get("economy") or {}
    out = []
    for element in (version.report or {}).get("elements") or []:
        if element.get("type") not in GIVEABLE:
            continue
        economy = {**(element.get("economy") or {}), **(decided.get(element.get("product")) or {})}
        out.append(
            {
                "product": element.get("product"),
                "type": element["type"],
                "look": element.get("look"),
                "kind": element.get("kind"),
                "names": element.get("names") or {},
                "widget": widget_render(element),
                "contracts": element.get("contracts") or [],
                "sold": economy.get("sold", True),
                "price": economy.get("price"),
                "rarity": economy.get("rarity") or "common",
            }
        )
    return out


def _blocked(row: PackVersion) -> bool:
    return "blocking" in (row.outcomes.get("analysis"), row.outcomes.get("security"))


def _version_row(row: PackVersion) -> dict[str, Any]:
    report = row.report or {}
    return {
        "version": row.version,
        "sha": row.sha256[:16],
        "step": row.step,
        "outcomes": row.outcomes,
        "summary": report.get("summary"),
        "names": (report.get("pack") or {}).get("names"),
        "author": (report.get("pack") or {}).get("author"),
        "license": (report.get("pack") or {}).get("license"),
        "decision": row.decision,
        "tested": bool(row.measures),
        "detected_at": row.detected_at.isoformat(timespec="seconds") if row.detected_at else None,
        "published_at": row.published_at.isoformat(timespec="seconds") if row.published_at else None,
        "ever_published": row.ever_published,
    }


def _plain(imported: Imported) -> dict[str, Any]:
    return {"pack": imported.pack, "version": imported.version, "sha": imported.sha, "new": imported.new}
