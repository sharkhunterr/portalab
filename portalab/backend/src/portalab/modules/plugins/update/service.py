"""Updates and rollback (T026; R10, FR-021/022/028): stage the new version beside the current one, check
compatibility and dependencies, run **expand-only** migrations (a destructive step is refused until a later
version), mark ``update_pending`` (the new code loads at the next restart) — confirming the restart
switches versions and starts a **probation** window; a failed health check (plugin errors during
probation, or a load failure) or a failed migration rolls back to the previous package automatically,
with the data intact (``plugin.update_failed`` / ``plugin.rolled_back``). History is never reinterpreted:
every version stays recorded."""

from datetime import timedelta
from pathlib import Path
from typing import Any

from packaging.version import Version
from sqlalchemy import func, select

from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict
from portalab.core.time import utc_now
from portalab.modules.plugins.compat.checker import check
from portalab.modules.plugins.lifecycle.service import SYSTEM, InvalidState, Lifecycle, PluginIncompatible
from portalab.modules.plugins.models import ErrorStat, Plugin, PluginVersion, UpdateRun, VersionState
from portalab.modules.plugins.observability import log
from portalab.modules.plugins.store.package import read_manifest


class Updates:
    def __init__(self, lifecycle: Lifecycle) -> None:
        self.lifecycle = lifecycle
        self.database = lifecycle.database
        self.clock = lifecycle.clock

    async def _run(self, key: str) -> UpdateRun | None:
        async with self.database.session() as session:
            run: UpdateRun | None = await session.scalar(
                select(UpdateRun)
                .where(UpdateRun.plugin_key == key, UpdateRun.status.in_(("pending_restart", "probation")))
                .order_by(UpdateRun.created_at.desc())
                .limit(1)
            )
        return run

    async def _set_version_status(self, key: str, version: str, status: str, probation: Any = None) -> None:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(VersionState, (key, version), with_for_update=True)
            if row is None:
                uow.session.add(
                    VersionState(
                        plugin_key=key,
                        version=version,
                        status=status,
                        probation_until=probation,
                        updated_at=utc_now(self.clock),
                    )
                )
            else:
                row.status, row.probation_until, row.updated_at = status, probation, utc_now(self.clock)

    async def stage(self, actor: Principal, key: str, source: Path) -> UpdateRun:
        plugin = await self.lifecycle.get(key)
        if plugin.state not in ("enabled", "disabled", "update_failed"):
            raise InvalidState("Only an enabled or disabled plugin can be updated.")
        manifest = read_manifest(source)
        if manifest.key != key:
            raise Conflict("This package is another plugin.", code="plugin.wrong_package")
        if Version(manifest.version) <= Version(plugin.current_version):
            raise Conflict("An update needs a newer version.", code="plugin.not_newer")
        incompatible = check(manifest, self.lifecycle.capabilities)
        if incompatible:
            raise PluginIncompatible(
                "The new version is not compatible with this portal.",
                extensions={"reasons": [f"{i.what}: {i.detail}" for i in incompatible]},
            )
        stored = self.lifecycle.store.extract(source)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            exists = await session.get(PluginVersion, (key, manifest.version))
            if exists is None:
                session.add(
                    PluginVersion(
                        plugin_key=key,
                        version=manifest.version,
                        manifest=manifest.raw,
                        package_path=str(stored.path),
                        sha256=stored.sha256,
                        status="staged",
                        installed_at=now,
                    )
                )
            run = UpdateRun(
                plugin_key=key,
                from_version=plugin.current_version,
                to_version=manifest.version,
                status="staged",
                created_at=now,
                updated_at=now,
            )
            session.add(run)
        await self._set_version_status(key, manifest.version, "staged")
        try:
            await self.lifecycle.storage.provision(key, self.lifecycle.config().statement_timeout_ms)
            await self.lifecycle.storage.migrate(
                key, stored.path, manifest.raw.get("migrations"), expand_only=True
            )
        except Exception as error:
            await self._finish(run.id, "failed", f"{type(error).__name__}: {str(error)[:200]}")
            await self._set_version_status(key, manifest.version, "failed")
            await self.lifecycle._transition(actor, key, plugin.state, "update_failed", "migration failed")
            raise
        await self._finish(run.id, "pending_restart")
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Plugin, key, with_for_update=True)
            assert row is not None
            row.needs_restart = True
        await self.lifecycle._transition(
            actor, key, "update_pending", "configuration_changed", f"update to {manifest.version}"
        )
        return await self._get(run.id)

    async def _get(self, run_id: Any) -> UpdateRun:
        async with self.database.session() as session:
            run = await session.get(UpdateRun, run_id)
        assert run is not None
        return run

    async def _finish(
        self, run_id: Any, status: str, error: str | None = None, probation: Any = None
    ) -> None:
        async with self.database.unit_of_work() as uow:
            run = await uow.session.get(UpdateRun, run_id, with_for_update=True)
            assert run is not None
            run.status, run.updated_at = status, utc_now(self.clock)
            if error is not None:
                run.error = error
            if probation is not None:
                run.probation_until = probation

    async def _switch(self, key: str, version: str) -> None:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Plugin, key, with_for_update=True)
            assert row is not None
            row.current_version, row.needs_restart, row.updated_at = version, False, utc_now(self.clock)

    async def confirm_restart(self, actor: Principal, key: str) -> UpdateRun:
        """The graceful restart: the new version takes over and is watched during probation."""
        run = await self._run(key)
        if run is None or run.status != "pending_restart":
            raise InvalidState("No update waits for a restart.")
        await self.lifecycle.registries.remove(f"plugin:{key}")
        await self.lifecycle.ledger.removed(key)
        await self._switch(key, run.to_version)
        probation = utc_now(self.clock) + timedelta(
            minutes=max(1, self.lifecycle.config().update_probation_minutes)
        )
        try:
            await self.lifecycle._register(key, with_code=True)
        except Exception as error:
            log.warning("updated plugin failed to load", extra={"fields": {"plugin": key}})
            await self._finish(run.id, "probation", probation=probation)
            return await self.rollback(SYSTEM, key, f"load failed: {type(error).__name__}")
        await self._set_version_status(key, run.from_version, "previous")
        await self._set_version_status(key, run.to_version, "probation", probation)
        await self._finish(run.id, "probation", probation=probation)
        await self.lifecycle._transition(actor, key, "enabled", "enabled", f"probation of {run.to_version}")
        return await self._get(run.id)

    async def _errors_since(self, key: str, since: Any) -> int:
        async with self.database.session() as session:
            return int(
                await session.scalar(
                    select(func.coalesce(func.sum(ErrorStat.count), 0)).where(
                        ErrorStat.plugin_key == key, ErrorStat.window_start >= since - timedelta(minutes=10)
                    )
                )
                or 0
            )

    async def rollback(
        self, actor: Principal, key: str, reason: str = "rolled back by the Admin"
    ) -> UpdateRun:
        run = await self._run(key)
        if run is None:
            raise InvalidState("No update to roll back.")
        await self.lifecycle.registries.remove(f"plugin:{key}")
        await self.lifecycle.ledger.removed(key)
        await self._switch(key, run.from_version)
        await self._set_version_status(key, run.to_version, "failed")
        await self._set_version_status(key, run.from_version, "current")
        await self.lifecycle._register(key, with_code=True)
        await self._finish(run.id, "rolled_back", reason[:300])
        await self.lifecycle._transition(actor, key, "enabled", "update_failed", reason)
        await self.lifecycle._transition(actor, key, "enabled", "rolled_back", reason)
        return await self._get(run.id)

    async def probation(self) -> int:
        """Job: settle every update whose probation is over — success, or rollback on errors."""
        now = utc_now(self.clock)
        async with self.database.session() as session:
            runs = list(
                (
                    await session.execute(
                        select(UpdateRun).where(
                            UpdateRun.status == "probation", UpdateRun.probation_until <= now
                        )
                    )
                ).scalars()
            )
        for run in runs:
            plugin = await self.lifecycle.get(run.plugin_key)
            assert run.probation_until is not None
            started = run.probation_until - timedelta(
                minutes=max(1, self.lifecycle.config().update_probation_minutes)
            )
            if plugin.state != "enabled" or await self._errors_since(run.plugin_key, started) > 0:
                await self.rollback(SYSTEM, run.plugin_key, "failed its probation")
                continue
            await self._finish(run.id, "succeeded")
            await self._set_version_status(run.plugin_key, run.to_version, "current")
            await self.lifecycle._transition(
                SYSTEM, run.plugin_key, "enabled", "updated", f"updated to {run.to_version}"
            )
        return len(runs)
