"""Built-in Control Center panels (T024, T029; 027 T094). Domain panels are contributed by their owning
modules through the ``admin.panel`` capability (observability 025 provides the health overview). The
services panel reads 005/006 through their capabilities and the storage panel measures the database; a
missing capability renders as ``unavailable`` so the layout stays stable."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from portalab.capabilities.administration import AUDIT_STATUS_CAPABILITY, PanelResult
from portalab.capabilities.health import SERVICE_DIRECTORY, SERVICE_STATE
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now


class ConfigurationPanel:
    """First real panel: setup completion, active policies, invalid stored values."""

    def __init__(self, first_run: Any, policies: Any, metrics_snapshot: Any) -> None:
        self.first_run = first_run
        self.policies = policies
        self.metrics_snapshot = metrics_snapshot

    async def panel(self, principal: Principal) -> PanelResult:
        invalid = int(self.metrics_snapshot().get("admin.config.invalid_stored_values", 0))
        return PanelResult(
            "partial" if invalid else "available",
            {
                "first_run_completed": await self.first_run.completed(),
                "active_policies": len(await self.policies.active()),
                "invalid_stored_values": invalid,
            },
        )


class AuditPanel:
    """Audit chain status, fed by the ``audit.status`` capability (spec 021 completion in authz)."""

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def panel(self, principal: Principal) -> PanelResult:
        providers = self.capabilities.system_providers(AUDIT_STATUS_CAPABILITY)
        if not providers:
            return PanelResult("unavailable", {"reason": "not_installed"})
        status: Mapping[str, Any] = await providers[0].provider.status()
        return PanelResult("available" if status.get("verified", True) else "partial", dict(status))


class ServicesPanel:
    """027 T094: how the connected services are doing (counts per health state) — the first place an
    administrator looks after installation, with the way to add one when there is none."""

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def panel(self, principal: Principal) -> PanelResult:
        directory = self.capabilities.system_providers(SERVICE_DIRECTORY)
        states = self.capabilities.system_providers(SERVICE_STATE)
        if not directory or not states:
            return PanelResult("unavailable", {"reason": "not_installed"})
        services = await directory[0].provider.services()
        views = {v.service_id: str(v.state) for v in await states[0].provider.all()}
        counts: dict[str, int] = {}
        for service in services:
            state = views.get(service.id, "unknown")
            counts[state] = counts.get(state, 0) + 1
        troubled = sum(n for state, n in counts.items() if state in ("degraded", "unavailable", "down"))
        return PanelResult(
            "partial" if troubled else "available",
            {"total": len(services), "by_state": counts, "troubled": troubled},
        )


class StoragePanel:
    """027 T094: database size and its largest schemas (what grows, at a glance). Sizes come from the
    catalog (``relpages`` of tables, indexes and their TOAST, kept current by autovacuum) rather than a
    filesystem walk, and are cached a few minutes: the panel stays well inside the Control Center budget."""

    TTL = timedelta(minutes=5)

    def __init__(self, database: Database, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock
        self._cached: tuple[datetime, PanelResult] | None = None

    async def panel(self, principal: Principal) -> PanelResult:
        now = utc_now(self.clock)
        if self._cached is not None and now - self._cached[0] < self.TTL:
            return self._cached[1]
        async with self.database.session() as session:
            total = int(await session.scalar(text("SELECT pg_database_size(current_database())")) or 0)
            rows = (
                await session.execute(
                    text(
                        "SELECT coalesce(owner.nspname, n.nspname) AS schema, "
                        "sum(c.relpages)::bigint * current_setting('block_size')::bigint AS size "
                        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "LEFT JOIN pg_class base ON base.reltoastrelid = c.oid "
                        "LEFT JOIN pg_namespace owner ON owner.oid = base.relnamespace "
                        "WHERE c.relkind IN ('r', 'i', 't', 'm') "
                        "AND n.nspname NOT IN ('pg_catalog', 'information_schema') "
                        "GROUP BY 1 HAVING coalesce(owner.nspname, n.nspname) NOT LIKE 'pg_toast%' "
                        "AND coalesce(owner.nspname, n.nspname) NOT IN ('pg_catalog', 'information_schema') "
                        "ORDER BY size DESC LIMIT 5"
                    )
                )
            ).all()
        result = PanelResult(
            "available",
            {"database_bytes": total, "largest": [{"schema": r[0], "bytes": int(r[1])} for r in rows]},
        )
        self._cached = (now, result)
        return result
