"""The confined plugins of one Portalab process (spec 030): their hosts, their grants, their requests.

Each enabled confined plugin gets a :class:`ConfinedHost` (its process). Everything the process asks goes
through :meth:`ConfinedRuntime.ask`, which checks the capability against the grants of the running version
before the request reaches its handler (storage, portal data, network, live channels, notifications,
events, jobs); a refused request and every limit a plugin breaks is an **attempt**, recorded and counted by
023's guard toward quarantine.
"""

from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from portalab.capabilities.registry import CapabilityRegistry
from portalab.core import egress
from portalab.core.confinement import Support, probe
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.secrets import SecretBox
from portalab.core.time import Clock, utc_now
from portalab.modules.plugins.confined.grants import Grants
from portalab.modules.plugins.confined.host import ConfinedHost, Denied, Exposed, HostConfig
from portalab.modules.plugins.confined.network import Network
from portalab.modules.plugins.confined.portal import PortalCalls
from portalab.modules.plugins.confined.replay import Registered
from portalab.modules.plugins.confined.services import Services
from portalab.modules.plugins.confined.storage import PluginDatabase, StatementRefused
from portalab.modules.plugins.guard.guard import PluginGuard
from portalab.modules.plugins.manifest.schema import Manifest
from portalab.modules.plugins.models import Attempt
from portalab.modules.plugins.observability import log, metrics

# the capability each request of a plugin's process needs
REQUIRES = {
    "db.execute": "storage",
    "portal.call": "portal_data",
    "http.request": "network",
    "live.publish": "live",
    "notify": "notifications",
    "events.emit": "events",
    "jobs.enqueue": "jobs",
}
# attempts already counted by 023's guard through the failed call they end
COUNTED_BY_CALL = {"timeout", "busy", "oversize"}

# (plugin key, its manifest, the grant's parameters, the request's arguments, the member it acts for)
Handler = Callable[[str, Manifest, Mapping[str, Any], Mapping[str, Any], Any], Awaitable[Any]]


class ConfinedRuntime:
    def __init__(
        self,
        database: Database,
        guard: PluginGuard,
        grants: Grants,
        config: Callable[[], Any],
        *,
        box: SecretBox | None = None,
        run_root: Path | None = None,
        forbidden: tuple[Path, ...] = (),
        clock: Clock | None = None,
        role_prefix: str = "plugin_",
        events: EventPublisher | None = None,
        capabilities: CapabilityRegistry | None = None,
    ) -> None:
        self.database = database
        self.guard = guard
        self.grants = grants
        self.config = config
        self.box = box
        self.run_root = run_root or Path("plugins-run")
        self.forbidden = forbidden
        self.clock = clock
        self.storage = PluginDatabase(database, box, role_prefix=role_prefix)
        self.hosts: dict[str, ConfinedHost] = {}
        self.manifests: dict[str, Manifest] = {}
        self.versions: dict[str, str] = {}
        self.registered: dict[str, Registered] = {}
        self.portal = PortalCalls()
        self.network = Network(database, box, clock=clock)
        self.services = Services(database, events, capabilities, clock=clock)
        self.handlers: dict[str, Handler] = {
            "db.execute": self._db,
            "portal.call": self._portal,
            "http.request": self._network,
            "notify": self.services.notify,
            "events.emit": self.services.emit,
            "jobs.enqueue": self.services.enqueue_job,
            "live.publish": self.services.live,
        }
        self._support: Support | None = None

    # --- the kernel ------------------------------------------------------------------------------------
    def support(self) -> Support:
        if self._support is None:
            self._support = probe()
        return self._support

    def can_run(self) -> tuple[bool, bool]:
        """(may confined plugins run here, in the weaker mode)."""
        support = self.support()
        if support.ok:
            return True, False
        return bool(self.config().allow_weak_confinement), True

    # --- processes -------------------------------------------------------------------------------------
    async def start(
        self, key: str, version: str, package: Path, manifest: Manifest, settings: Mapping[str, Any]
    ) -> ConfinedHost:
        await self.stop(key)
        ok, weak = self.can_run()
        if not ok:
            raise PermissionError("this system cannot confine plugins and the weaker mode is off")
        config = self.config()
        host = ConfinedHost(
            HostConfig(
                key=key,
                version=version,
                package=package,
                entry_point=str(manifest.entry_point),
                scratch=self.run_root / key,
                settings=dict(settings),
                memory_mb=int(config.memory_mb),
                weak=weak,
                deadline_s=float(config.hook_timeout_seconds),
                concurrency=int(config.concurrent_calls),
                forbidden=self.forbidden,
            ),
            lambda cap, args, acting: self.ask(key, cap, args, acting),
            lambda kind, detail: self.attempt(key, kind, detail),
        )
        self.hosts[key] = host
        self.manifests[key] = manifest
        for listed in manifest.network_hosts:  # 030: hosts the Admin accepted are known to the allow-list
            egress.EGRESS.allow(listed["host"], f"plugin:{key}")
        self.versions[key] = version
        await host.start()
        return host

    async def stop(self, key: str) -> None:
        host = self.hosts.pop(key, None)
        self.registered.pop(key, None)
        egress.EGRESS.forget(f"plugin:{key}")
        if host is not None:
            await host.stop()
        await self.storage.close(key)

    async def stop_all(self) -> None:
        for key in list(self.hosts):
            await self.stop(key)

    # --- requests of a plugin's process ---------------------------------------------------------------
    async def ask(self, key: str, cap: str, args: Mapping[str, Any], acting: Any = None) -> Any:
        manifest, version = self.manifests.get(key), self.versions.get(key)
        if manifest is None or version is None:
            raise Denied("denied", "the plugin is not running")
        need = REQUIRES.get(cap)
        if need is None:
            await self.attempt(key, "denied_capability", {"request": cap[:40]})
            raise Denied("denied", f"{cap} does not exist")
        granted = await self.grants.active(key, version)
        if need not in granted:
            await self.attempt(key, "denied_capability", {"capability": need})
            raise Denied("denied", f"the {need} capability is not granted")
        handler = self.handlers.get(cap)
        if handler is None:
            raise Denied("unavailable", f"{cap} is not available yet")
        metrics.increment(f"plugins.confined.ask.{need}")
        return await handler(key, manifest, granted[need], args, acting)

    async def _db(
        self, key: str, manifest: Manifest, grant: Mapping[str, Any], args: Mapping[str, Any], acting: Any
    ) -> Any:
        config = self.config()
        quota = int(grant.get("quota_mb") or config.storage_quota_mb)
        try:
            return await self.storage.execute(
                key,
                str(args.get("sql", "")),
                dict(args.get("params") or {}),
                timeout_ms=int(config.statement_timeout_ms),
                quota_mb=quota,
            )
        except StatementRefused as error:
            if error.code in ("denied_statement", "storage_quota", "timeout"):
                await self.attempt(key, error.code, {"reason": str(error)[:120]})
            raise Denied(error.code, str(error)) from None

    async def _portal(
        self, key: str, manifest: Manifest, grant: Mapping[str, Any], args: Mapping[str, Any], acting: Any
    ) -> Any:
        try:
            return await self.portal(key, manifest, grant, args, acting)
        except Denied as error:
            if error.code == "denied_operation":
                await self.attempt(
                    key, "denied_operation", {"operation": str(args.get("operation", ""))[:96]}
                )
            raise

    async def _network(
        self, key: str, manifest: Manifest, grant: Mapping[str, Any], args: Mapping[str, Any], acting: Any
    ) -> Any:
        try:
            return await self.network(key, manifest, grant, args, acting)
        except Denied as error:
            if error.code in ("denied_host", "private_address", "rate"):
                await self.attempt(key, error.code, {"reason": str(error)[:120]})
            raise

    # --- attempts --------------------------------------------------------------------------------------
    async def attempt(self, key: str, kind: str, detail: Mapping[str, Any]) -> None:
        version = self.versions.get(key, "?")
        safe = {k: v for k, v in dict(detail).items() if isinstance(v, (str, int, float, bool, type(None)))}
        try:
            async with self.database.unit_of_work() as uow:
                uow.session.add(
                    Attempt(
                        plugin_key=key,
                        version=version,
                        kind=kind,
                        detail={k: (v[:200] if isinstance(v, str) else v) for k, v in safe.items()},
                        occurred_at=utc_now(self.clock),
                    )
                )
        except Exception:
            log.warning("plugin attempt not recorded", extra={"fields": {"plugin": key, "kind": kind}})
        metrics.increment(f"plugins.confined.attempt.{kind}")
        if kind not in COUNTED_BY_CALL:
            await self.guard.record(key, "hook", f"refused: {kind}")

    # --- helpers for 023's registries ----------------------------------------------------------------
    @staticmethod
    def consumer(handler: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        """An event consumer: its context is handed with ``idempotent_effect`` only."""

        async def consume(envelope: Any, context: Any) -> Any:
            return await handler(envelope, Exposed(context, ("idempotent_effect",), ("replay", "as_of")))

        return consume
