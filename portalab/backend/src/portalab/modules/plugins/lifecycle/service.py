"""Plugin lifecycle (T014; R2, R6, R8): ``installed → (needs_configuration) → enabled ⇄ disabled →
archived`` plus ``incompatible`` and ``quarantined`` (and ``update_pending``/``update_failed`` for updates).

* install: manifest validation, import scan for code plugins, package extracted with its checksum, a
  review object the Admin must approve (consent record) before enabling;
* enable: approval, compatibility (portal + capabilities), dependencies, checksum, schema/role
  provisioning and migrations with the plugin role, then contributions — declarative ones at once, code
  ones at the next (graceful) restart (``needs_restart``), since Python cannot unload modules;
* disable/quarantine: every contribution removed from every registry (ledger sweep), data untouched;
  disabling with enabled dependents is refused unless the Admin confirms the cascade;
* every transition is permissioned (API), audited and emits ``plugin.<event>`` and ``plugin.state_changed``
  (dedup ``(plugin_key, seq)``)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import select

from portalab.capabilities.administration import PLUGIN_PERMISSIONS_CAPABILITY
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, WithPermission
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.visuals import PluginVisualType, plugin_visual_types
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.plugins.compat.checker import check
from portalab.modules.plugins.confined.grants import review_items
from portalab.modules.plugins.confined.replay import replay
from portalab.modules.plugins.confined.runtime import ConfinedRuntime
from portalab.modules.plugins.context.plugin_context import Context, apply_manifest
from portalab.modules.plugins.context.registries import Registries
from portalab.modules.plugins.contributions.ledger_store import Ledger
from portalab.modules.plugins.db.plugin_db import PluginStorage
from portalab.modules.plugins.guard.guard import PluginGuard
from portalab.modules.plugins.lifecycle import loader
from portalab.modules.plugins.manifest.schema import Manifest, validate
from portalab.modules.plugins.models import Plugin, PluginVersion, Review, VersionState
from portalab.modules.plugins.observability import log, metrics
from portalab.modules.plugins.permissions import MANAGE
from portalab.modules.plugins.resolver.resolver import dependents, load_order, problems_for
from portalab.modules.plugins.scanner.scanner import scan_package
from portalab.modules.plugins.store.package import PackageError, PackageStore, read_manifest

SYSTEM = Principal(channel="system")
ENABLE_FROM = (
    "installed",
    "disabled",
    "needs_configuration",
    "incompatible",
    "quarantined",
    "held_unconfined",
    "held_confinement",
)


class PluginNotFound(NotFound):
    default_code = "plugin.not_found"
    default_title = "Plugin not found"


class PluginIncompatible(Conflict):
    default_code = "plugin.incompatible"
    default_title = "Incompatible plugin"


class DependencyMissing(Conflict):
    default_code = "plugin.dependency_missing"
    default_title = "Missing dependency"


class HasDependents(Conflict):
    default_code = "plugin.has_dependents"
    default_title = "Other plugins depend on it"


class InvalidState(Conflict):
    default_code = "plugin.invalid_state"
    default_title = "Not possible in this state"


class Held(Conflict):
    """030: the plugin cannot run here (its code would run in Portalab's process, or cannot be confined)."""

    default_code = "plugin.held"
    default_title = "This plugin is held"

    def __init__(self, state: str, message: str) -> None:
        super().__init__(message, code=f"plugin.{state}")
        self.state = state


class CapabilitiesNotGranted(Forbidden):
    default_code = "plugin.capabilities_not_granted"
    default_title = "Capabilities not granted"


def review_of(manifest: Manifest, sha256: str) -> dict[str, Any]:
    raw = manifest.raw
    return {
        "key": manifest.key,
        "name": manifest.name,
        "version": manifest.version,
        "scope": manifest.scope,
        "maturity": manifest.maturity,
        "code": manifest.entry_point is not None,
        "permissions": manifest.permission_keys()
        + ([f"plugin:{manifest.key}.use"] if manifest.scope == "user" else []),
        "extension_points": manifest.extension_points,
        "events": {
            "produces": manifest.event_types(),
            "consumes": list(raw.get("events", {}).get("consumes", [])),
        },
        "personal_data": manifest.personal_data,
        "capabilities": {
            "requires": manifest.requires_capabilities,
            "provides": list(raw.get("capabilities_provided", [])),
        },
        "requires_plugins": manifest.requires_plugins,
        "schema": f"plugin_{manifest.key}",
        "migrations": raw.get("migrations"),
        "sha256": sha256,
        # 030: where its code runs, and what the Admin grants by approving
        "runtime": manifest.runtime,
        "requested_capabilities": review_items(manifest) if manifest.schema_version >= 2 else [],
        "routes": manifest.routes,
    }


class Lifecycle:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        registries: Registries,
        store: PackageStore,
        storage: PluginStorage,
        ledger: Ledger,
        guard: PluginGuard,
        config: Callable[[], Any],
        *,
        clock: Clock | None = None,
        runtime: ConfinedRuntime | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.registries = registries
        self.store = store
        self.storage = storage
        self.ledger = ledger
        self.guard = guard
        self.config = config
        self.clock = clock
        self.runtime = runtime
        guard.on_threshold = self.quarantine

    # --- reads -------------------------------------------------------------------------------------------
    async def get(self, key: str) -> Plugin:
        async with self.database.session() as session:
            plugin = await session.get(Plugin, key)
        if plugin is None:
            raise PluginNotFound("This plugin is not installed.")
        return plugin

    async def all(self) -> list[Plugin]:
        async with self.database.session() as session:
            return list((await session.execute(select(Plugin).order_by(Plugin.key))).scalars())

    async def version(self, key: str, version: str) -> PluginVersion:
        async with self.database.session() as session:
            row = await session.get(PluginVersion, (key, version))
        if row is None:
            raise PluginNotFound("This plugin version is not installed.")
        return row

    async def manifests(self) -> dict[str, Manifest]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(PluginVersion)
                    .join(
                        Plugin,
                        (Plugin.key == PluginVersion.plugin_key)
                        & (Plugin.current_version == PluginVersion.version),
                    )
                    .where(Plugin.state != "archived")
                )
            ).scalars()
            return {r.plugin_key: validate(dict(r.manifest)) for r in rows}

    async def enabled_keys(self) -> set[str]:
        return {p.key for p in await self.all() if p.state == "enabled"}

    # --- transitions -------------------------------------------------------------------------------------
    async def _transition(
        self, actor: Principal, key: str, state: str, event: str, reason: str | None = None
    ) -> Plugin:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            plugin = await session.get(Plugin, key, with_for_update=True)
            if plugin is None:
                raise PluginNotFound("This plugin is not installed.")
            source = plugin.state
            plugin.state, plugin.updated_at = state, now
            plugin.state_seq += 1
            if state == "enabled":
                plugin.enabled_at, plugin.quarantine_reason = now, None
            if state == "quarantined":
                plugin.quarantine_reason, plugin.last_error_at = (reason or "")[:300], now
            await self.events.publish(
                session,
                f"plugin.{event}",
                {"plugin": key, "version": plugin.current_version},
                occurred_at=now,
                actor=actor,
                subject=SubjectRef("plugin", key),
                dedup_key=f"plugin.{event}:{key}:{plugin.state_seq}",
            )
            await self.events.publish(
                session,
                "plugin.state_changed",
                {
                    "plugin_id": key,
                    "plugin": key,
                    "from_state": source,
                    "state": "disabled" if state in ("quarantined", "archived") else state,
                    "reason": (reason or None) and reason[:200],
                    "seq": plugin.state_seq,
                },
                occurred_at=now,
                actor=actor,
                subject=SubjectRef("plugin", key),
                dedup_key=f"plugin.state_changed:{key}:{plugin.state_seq}",
            )
            await self.audit.record(
                session,
                AuditRecord(
                    action=f"plugin.{event}",
                    actor=actor,
                    resource=ResourceRef("plugin", key),
                    decision="allow",
                    context={"from": source, "to": state, "reason": (reason or "")[:200]},
                    sensitive=True,
                ),
            )
        metrics.increment(f"plugins.transitions.{event}")
        return plugin

    async def install(
        self, actor: Principal, source: Path, *, origin: str = "admin_upload"
    ) -> tuple[Plugin, dict[str, Any]]:
        manifest = read_manifest(source)
        async with self.database.session() as session:
            if await session.get(Plugin, manifest.key) is not None:
                raise Conflict("This plugin is installed already; update it instead.", code="plugin.exists")
        stored = self.store.extract(source)
        if manifest.entry_point and manifest.runtime == "in_process":  # confined code: the kernel confines it
            findings = scan_package(stored.path, manifest.entry_point.split(":")[0].split(".")[0])
            if findings:
                raise PackageError(
                    "The plugin code uses forbidden imports or calls.",
                    code="plugin.forbidden_code",
                    extensions={"findings": [f"{f.path}:{f.line} {f.problem}" for f in findings[:20]]},
                )
        now = utc_now(self.clock)
        review = review_of(manifest, stored.sha256)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            session.add(
                Plugin(
                    key=manifest.key,
                    name=manifest.name,
                    scope=manifest.scope,
                    maturity=manifest.maturity,
                    state="installed",
                    current_version=manifest.version,
                    source=origin,
                    needs_restart=False,
                    approved=not self.config().require_review,
                    installed_by=actor.acting_for or actor.user_id,
                    installed_at=now,
                    updated_at=now,
                    runtime=manifest.runtime,
                    predates_confinement=False,
                )
            )
            await session.flush()
            session.add(
                PluginVersion(
                    plugin_key=manifest.key,
                    version=manifest.version,
                    manifest=manifest.raw,
                    package_path=str(stored.path),
                    sha256=stored.sha256,
                    status="current",
                    installed_at=now,
                )
            )
            session.add(
                VersionState(
                    plugin_key=manifest.key, version=manifest.version, status="current", updated_at=now
                )
            )
        plugin = await self._transition(actor, manifest.key, "installed", "installed")
        return plugin, review

    async def approve(self, actor: Principal, key: str) -> Plugin:
        plugin = await self.get(key)
        row = await self.version(key, plugin.current_version)
        manifest = validate(dict(row.manifest))
        review = review_of(manifest, row.sha256)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            current = await session.get(Plugin, key, with_for_update=True)
            assert current is not None
            current.approved = True
            session.add(
                Review(
                    plugin_key=key,
                    version=plugin.current_version,
                    approved_by=actor.acting_for or actor.user_id,
                    approved_at=utc_now(self.clock),
                    permissions=review["permissions"],
                    extension_points=review["extension_points"],
                    events=review["events"],
                    personal_data=review["personal_data"],
                    capabilities=[review["capabilities"]],
                )
            )
            current.runtime = manifest.runtime
            await self.audit.record(
                session,
                AuditRecord(
                    action="plugin.approved",
                    actor=actor,
                    resource=ResourceRef("plugin", key),
                    decision="allow",
                    context={"version": plugin.current_version, "sha256": row.sha256},
                    sensitive=True,
                ),
            )
        if self.runtime is not None and manifest.schema_version >= 2:
            await self.runtime.grants.grant_all(actor, key, plugin.current_version, manifest)
        return await self.get(key)

    async def _permissions(self, key: str, enabled: bool) -> None:
        for registration in self.capabilities.system_providers(PLUGIN_PERMISSIONS_CAPABILITY):
            try:
                await registration.provider.set_enabled(key, enabled)
            except Exception:
                log.warning("plugin permissions not synchronized", extra={"fields": {"plugin": key}})

    async def _register(self, key: str, *, with_code: bool) -> bool:
        """Contribute to the registries; returns whether code still waits for a restart."""
        plugin = await self.get(key)
        row = await self.version(key, plugin.current_version)
        manifest = validate(dict(row.manifest))
        package = self.store.verify(key, row.version, row.sha256)
        priority = int(self.config().contribution_priority.get(key, 100))
        db = self.storage.bound(key, self.config().statement_timeout_ms)  # issue 396: its own connections
        ctx = Context(key, self.registries, self.guard, db, priority=priority)
        apply_manifest(ctx, manifest.raw)
        self._visual_types(key, manifest)
        waiting = False
        if manifest.runtime == "confined":
            await self._register_confined(ctx, key, row.version, package, manifest)
        elif manifest.entry_point:
            if not self._unconfined_allowed(plugin):
                raise Held(
                    "held_unconfined",
                    "This plugin's code would run inside Portalab: use a confined version or allow it.",
                )
            if with_code or loader.loaded(manifest.entry_point, package):
                register = loader.load(manifest.entry_point, package)

                async def call() -> None:
                    result = register(ctx)
                    if hasattr(result, "__await__"):
                        await result

                await self.guard.run(key, "load", call)
            else:
                waiting = True
        await ctx.flush()
        for point, contribution_id, state, detail in ctx.recorded:
            await self.ledger.record(
                key, point, contribution_id, priority=priority, state=state, detail=detail
            )
        return waiting

    def _visual_types(self, key: str, manifest: Manifest) -> None:
        """030: the kinds of visuals it draws — packs may then bring looks of them (028 analysis)."""
        owner = f"plugin:{key}"
        plugin_visual_types.remove(owner)
        for item in manifest.visual_types:
            kinds = frozenset(item.get("render") or ["css"])
            plugin_visual_types.register(
                PluginVisualType(
                    f"plugin:{key}.{item['key']}",
                    owner,
                    str(item["label_key"]),
                    kinds,
                    item.get("icon"),
                    manifest.name,
                )
            )

    def _unconfined_allowed(self, plugin: Plugin) -> bool:
        mode = str(getattr(self.config(), "unconfined", "existing"))
        return mode == "allow" or (mode == "existing" and bool(plugin.predates_confinement))

    async def _register_confined(
        self, ctx: Context, key: str, version: str, package: Path, manifest: Manifest
    ) -> None:
        if self.runtime is None:
            raise Held("held_confinement", "Confined plugins are not available in this process.")
        ok, _weak = self.runtime.can_run()
        if not ok:
            raise Held("held_confinement", "This system cannot confine plugins (and the weaker mode is off).")
        missing = await self.runtime.grants.missing(key, version, manifest)
        if missing and await self.runtime.grants.carry_over(key, version, manifest):
            missing = []  # an update asking nothing more keeps what the Admin granted
        if missing:
            raise CapabilitiesNotGranted(
                "Review the plugin and accept its capabilities first.", extensions={"missing": missing}
            )
        host = await self.runtime.start(key, version, package, manifest, self._settings_of(key, manifest))
        granted = await self.runtime.grants.active(key, version)
        pending: list[tuple[str, str]] = []
        registered = replay(
            ctx,
            manifest,
            host.calls,
            granted,
            lambda method, why: pending.append((method, why)),
            wrap_consumer=self.runtime.consumer,
        )
        self.runtime.registered[key] = registered
        for method, why in pending:
            await self.runtime.attempt(key, "denied_capability", {"registration": method, "why": why})
        async with self.database.unit_of_work() as uow:
            current = await uow.session.get(Plugin, key, with_for_update=True)
            if current is not None:
                current.confinement = dict(host.confinement)
                current.runtime = "confined"

    def _settings_of(self, key: str, manifest: Manifest) -> dict[str, Any]:
        """The plugin's non-secret settings (defaults; the values set by the Admin when available)."""
        values: dict[str, Any] = {}
        for setting in manifest.raw.get("settings", []):
            if not setting.get("secret"):
                values[str(setting["name"])] = setting.get("default")
        return values

    async def _hold(self, key: str, held: Held) -> None:
        await self._transition(SYSTEM, key, held.state, held.state, str(held)[:300])

    async def enable(self, actor: Principal, key: str) -> Plugin:
        plugin = await self.get(key)
        if plugin.state not in ENABLE_FROM:
            raise InvalidState(f"A plugin cannot be enabled from {plugin.state}.")
        if self.config().require_review and not plugin.approved:
            raise Forbidden("Review and approve the plugin first.", code="plugin.review_required")
        manifests = await self.manifests()
        manifest = manifests[key]
        incompatible = check(manifest, self.capabilities)
        if incompatible:
            await self._transition(actor, key, "incompatible", "disabled", "incompatible")
            raise PluginIncompatible(
                "This plugin is not compatible with this portal.",
                extensions={"reasons": [f"{i.what}: {i.detail}" for i in incompatible]},
            )
        problems = problems_for(key, manifests, await self.enabled_keys())
        if problems:
            raise DependencyMissing(
                "This plugin's dependencies are not satisfied.",
                code=f"plugin.{problems[0].code}",
                extensions={"problems": [p.detail for p in problems]},
            )
        row = await self.version(key, plugin.current_version)
        package = self.store.verify(key, row.version, row.sha256)
        await self.storage.provision(key, self.config().statement_timeout_ms)
        await self.storage.migrate(key, package, manifest.raw.get("migrations"), expand_only=False)
        try:
            waiting = await self._register(key, with_code=False)
        except Held as held:
            await self.registries.remove(f"plugin:{key}")
            await self._hold(key, held)
            raise
        await self._permissions(key, True)
        async with self.database.unit_of_work() as uow:
            current = await uow.session.get(Plugin, key, with_for_update=True)
            assert current is not None
            current.needs_restart = waiting
        return await self._transition(actor, key, "enabled", "enabled")

    async def _remove(self, key: str) -> dict[str, int]:
        plugin_visual_types.remove(f"plugin:{key}")
        if self.runtime is not None:
            await self.runtime.stop(key)
        removed = await self.registries.remove(f"plugin:{key}")
        await self.ledger.removed(key)
        await self._permissions(key, False)
        return removed

    async def disable(self, actor: Principal, key: str, *, cascade: bool = False) -> list[str]:
        plugin = await self.get(key)
        if plugin.state not in ("enabled", "needs_configuration", "update_failed"):
            raise InvalidState(f"A plugin cannot be disabled from {plugin.state}.")
        chain = dependents(key, await self.manifests(), await self.enabled_keys())
        if chain and not cascade:
            raise HasDependents("Other enabled plugins need this one.", extensions={"dependents": chain})
        for dependent in [*chain, key]:
            await self._remove(dependent)
            await self._transition(
                actor, dependent, "disabled", "disabled", "cascade" if dependent != key else None
            )
        return [*chain, key]

    async def archive(self, actor: Principal, key: str) -> Plugin:
        plugin = await self.get(key)
        if plugin.state not in ("installed", "disabled", "incompatible", "quarantined", "update_failed"):
            raise InvalidState("Disable the plugin before archiving it.")
        return await self._transition(actor, key, "archived", "archived")

    async def quarantine(self, key: str, reason: str) -> None:
        plugin = await self.get(key)
        if plugin.state == "quarantined":
            return
        if plugin.state == "enabled":
            await self._remove(key)
        await self._transition(SYSTEM, key, "quarantined", "quarantined", reason)
        providers = self.capabilities.system_providers(NOTIFY)
        if providers:
            try:
                await providers[0].provider.send(
                    CommunicationRequest(
                        category="plugins.quarantined",
                        template_key="plugins:notify.quarantined",
                        audience=WithPermission(MANAGE),
                        dedup_key=f"plugin.quarantined:{key}:{plugin.state_seq + 1}",
                        params={"plugin": plugin.name[:120], "reason": reason[:200]},  # issue 398
                        subject_ref=f"plugin:{key}",
                        action_url=f"/admin/plugins/{key}",
                    )
                )
            except Exception:
                log.warning("quarantine notification not sent")

    async def load_enabled(self) -> list[str]:
        """Startup (app and worker): load every enabled plugin, dependencies first; one failing plugin is
        quarantined and never stops the portal from starting."""
        if not self.config().enabled:
            return []
        manifests = await self.manifests()
        enabled = await self.enabled_keys()
        loaded: list[str] = []
        priority = dict(self.config().contribution_priority)
        for key in load_order({k: m for k, m in manifests.items() if k in enabled}, priority):
            try:
                await self.registries.remove(f"plugin:{key}")
                await self.ledger.removed(key)
                await self._register(key, with_code=True)
                await self._permissions(key, True)
                async with self.database.unit_of_work() as uow:
                    row = await uow.session.get(Plugin, key, with_for_update=True)
                    if row is not None:
                        row.needs_restart = False
                loaded.append(key)
            except Held as held:
                await self.registries.remove(f"plugin:{key}")
                await self._hold(key, held)
            except Exception as error:
                log.warning(
                    "plugin failed to load", extra={"fields": {"plugin": key, "error": type(error).__name__}}
                )
                await self.guard.record(key, "load", error)
                await self.quarantine(key, f"failed to load: {type(error).__name__}")
        return loaded
