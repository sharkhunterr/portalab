"""Plugins module facade (spec 023): the extension registry and lifecycle. Wires the package store, the
import scanner, the resolver and compatibility checker, per-plugin storage, the contribution ledger, the
guard (quarantine), the lifecycle, updates with probation and rollback, purge, discovery, first-party
module lifecycle and per-user activation for Marketplace plugin products. The core runs unchanged with
``plugins.enabled = false`` or no plugin at all (no import path from the core to plugins)."""

import contextlib
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete

from portalab.capabilities.administration import TOGGLE_HOOK_CAPABILITY
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.notifications import declare_category, default_categories
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservedComponent,
)
from portalab.capabilities.plugins import EXTENSION_ACTIVATION
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.secrets import SecretBox
from portalab.core.time import Clock, utc_now
from portalab.modules.plugins import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.plugins.activation.service import Activations
from portalab.modules.plugins.confined.confirmations import Confirmations
from portalab.modules.plugins.confined.grants import Grants
from portalab.modules.plugins.confined.runtime import ConfinedRuntime
from portalab.modules.plugins.confined.services import JOB_KIND as CONFINED_JOB
from portalab.modules.plugins.context.registries import Registries
from portalab.modules.plugins.contributions.ledger_store import Ledger
from portalab.modules.plugins.db.plugin_db import PluginStorage
from portalab.modules.plugins.discovery.service import Discovery
from portalab.modules.plugins.events import register_event_types
from portalab.modules.plugins.guard.guard import PluginGuard
from portalab.modules.plugins.lifecycle.service import Lifecycle
from portalab.modules.plugins.models import ErrorStat
from portalab.modules.plugins.modules.registry import ModuleRegistry
from portalab.modules.plugins.observability import log, metrics
from portalab.modules.plugins.purge.service import Purges
from portalab.modules.plugins.resolver.resolver import problems_for
from portalab.modules.plugins.settings import SETTINGS, PluginsConfig
from portalab.modules.plugins.store.package import PackageStore
from portalab.modules.plugins.update.service import Updates

OWNER = "module:plugins"
INSTANCE = "plugins"
CATEGORIES = {
    "plugins.quarantined": "plugins:category.quarantined",
    "plugins.update": "plugins:category.update",
}


class PluginsModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        root: Path | None = None,
        role_prefix: str = "plugin_",
        registries: Registries | None = None,
        secret_box: SecretBox | None = None,
        forbidden: tuple[Path, ...] = (),
    ) -> None:
        self.database = database
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.config = PluginsConfig()
        config = lambda: self.config  # noqa: E731
        self.root = root or Path(self.config.directory)
        self.registries = registries or Registries(capabilities)
        self.store = PackageStore(self.root)
        self.storage = PluginStorage(database, role_prefix=role_prefix)
        self.ledger = Ledger(database, clock=clock)
        self.guard = PluginGuard(database, config, clock=clock)
        # 030: confined plugins (one process each), their grants and their requests
        self.grants = Grants(database, audit, clock=clock)
        self.runtime = ConfinedRuntime(
            database,
            self.guard,
            self.grants,
            config,
            box=secret_box,
            run_root=self.root.parent / "plugins-run" if root is not None else Path("plugins-run"),
            forbidden=forbidden,
            clock=clock,
            role_prefix=role_prefix,
            events=events,
            capabilities=capabilities,
        )
        self.confirmations = Confirmations(database, clock=clock)
        self.lifecycle = Lifecycle(
            database,
            events,
            audit,
            capabilities,
            self.registries,
            self.store,
            self.storage,
            self.ledger,
            self.guard,
            config,
            clock=clock,
            runtime=self.runtime,
        )
        self.updates = Updates(self.lifecycle)
        self.purges = Purges(self.lifecycle)
        self.discovery = Discovery(self.lifecycle)
        self.activations = Activations(self.lifecycle)
        self.modules = ModuleRegistry(capabilities, self.registries.remove, self._plugin_problems)

    async def _plugin_problems(self, key: str) -> list[str]:
        manifests = await self.lifecycle.manifests()
        if key not in manifests:
            return []
        return [p.detail for p in problems_for(key, manifests, await self.lifecycle.enabled_keys())]

    def register(self) -> None:
        register_event_types(self.registries.event_types)
        for key, label in CATEGORIES.items():
            if default_categories.get(key) is None:
                declare_category(key, OWNER, label, default_channels=("portal", "email"))
        if not self.capabilities.system_providers(EXTENSION_ACTIVATION):
            self.capabilities.provide(
                EXTENSION_ACTIVATION, self.activations, instance_ref=INSTANCE, owner=OWNER
            )
        if not any(
            p.instance_ref == INSTANCE for p in self.capabilities.system_providers(TOGGLE_HOOK_CAPABILITY)
        ):
            self.capabilities.provide(
                TOGGLE_HOOK_CAPABILITY, self.modules, instance_ref=INSTANCE, owner=OWNER
            )
        default_retention_targets.register(
            RetentionTarget(
                "plugins.error_stats",
                "plugins.error_stats",
                "technical",
                "window_start",
                "delete",
                OWNER,
                window=lambda: timedelta(days=30),
            )
        )
        self.registries.observables.declare(
            ObservedComponent(
                "plugins",
                OWNER,
                label="Plugins",
                functional_checks=(Check("plugins", self.probe),),
                metrics=("plugins.errors.route", "plugins.errors.event", "plugins.transitions.quarantined"),
            )
        )
        self.registries.observables.declare_source("plugins.instances", self.components, owner=OWNER)

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def probation() -> None:
            await self.updates.probation()

        async def purge_stats() -> None:
            async with self.database.unit_of_work() as uow:
                await uow.session.execute(
                    delete(ErrorStat).where(ErrorStat.window_start < utc_now(self.clock) - timedelta(days=30))
                )

        async def confined_job(payload: dict[str, Any]) -> None:
            """030: a confined plugin's job, run in its process (dropped when the plugin no longer runs)."""
            plugin, job = str(payload.get("plugin", "")), str(payload.get("job", ""))
            registered = self.runtime.registered.get(plugin)
            if registered is None or job not in registered.jobs:
                return
            await self.guard.run(
                plugin, "job", registered.jobs[job]["handler"], dict(payload.get("payload") or {})
            )

        async def confined_tick() -> None:
            minute = int(utc_now(self.clock).timestamp() // 60)
            for plugin, registered in list(self.runtime.registered.items()):
                for job in registered.jobs.values():
                    every = job.get("every_minutes")
                    if every and minute % max(1, int(every)) == 0:
                        with contextlib.suppress(Exception):  # counted by the guard; the tick goes on
                            await self.guard.run(plugin, "job", job["handler"], {})

        jobs.register(
            CONFINED_JOB,
            confined_job,
            idempotency="the plugin's job is idempotent",
            owner=OWNER,
            timeout_seconds=90,
        )
        return [
            self.start,
            register_periodic(
                jobs, self.database, "plugins.confined_tick", timedelta(minutes=1), confined_tick, owner=OWNER
            ),
            register_periodic(
                jobs, self.database, "plugins.probation", timedelta(minutes=1), probation, owner=OWNER
            ),
            register_periodic(
                jobs, self.database, "plugins.error_stats", timedelta(hours=6), purge_stats, owner=OWNER
            ),
        ]

    async def start(self) -> None:
        """Process start (app and worker): settings, then every enabled plugin, dependencies first."""
        await self.refresh_config()
        try:
            await self.lifecycle.load_enabled()
        except Exception:
            log.warning("plugins not loaded at startup")

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("plugins configuration not refreshed")

    async def probe(self) -> CheckResult:
        plugins = await self.lifecycle.all()
        quarantined = [p.key for p in plugins if p.state == "quarantined"]
        facts = {
            "installed": len(plugins),
            "enabled": sum(1 for p in plugins if p.state == "enabled"),
            "quarantined": len(quarantined),
            "errors": int(sum(v for k, v in metrics.snapshot().items() if k.startswith("plugins.errors."))),
        }
        if quarantined:
            return CheckResult("degraded", f"quarantined: {', '.join(quarantined[:5])}", facts)
        return CheckResult("ok", "plugins healthy", facts)

    async def components(self) -> list[ObservedComponent]:
        out = []
        for plugin in await self.lifecycle.all():
            if plugin.state in ("enabled", "quarantined"):

                async def check(key: str = plugin.key) -> CheckResult:
                    current = await self.lifecycle.get(key)
                    stats = await self.guard.stats(key)
                    errors = sum(s.count for s in stats[:1])
                    if current.state == "quarantined":
                        return CheckResult(
                            "down", current.quarantine_reason or "quarantined", {"errors": errors}
                        )
                    return CheckResult("degraded" if errors else "ok", "plugin running", {"errors": errors})

                out.append(
                    ObservedComponent(
                        f"plugin:{plugin.key}",
                        f"plugin:{plugin.key}",
                        kind="plugin",
                        label=plugin.name,
                        functional_checks=(Check("plugin", check),),
                    )
                )
        return out
