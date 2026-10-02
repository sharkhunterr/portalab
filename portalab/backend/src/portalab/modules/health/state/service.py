"""State service (T007): gathers the deriver's inputs, writes ``service_state`` + ``state_history`` and
emits ``service.status_changed`` (``dimension="health"``) once per transition, deduplicated by
``(service, dimension, to_state, state_seq)``. Re-evaluation is idempotent: same inputs, no new row."""

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.health import SERVICE_DIRECTORY, ServiceInfo
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.health.models import HealthSample, MaintenanceWindow, ServiceState, StateHistory
from portalab.modules.health.observability import metric_part, metrics
from portalab.modules.health.settings import HealthConfig
from portalab.modules.health.state.deriver import RULES_VERSION, Derived, Inputs, Thresholds, derive

SYSTEM = Principal(channel="system")
RECENT = 20


class StateService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        *,
        config: HealthConfig | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.config = config or HealthConfig()
        self.clock = clock

    def thresholds(self) -> Thresholds:
        return Thresholds(
            degraded_latency_ms=self.config.degraded_latency_ms,
            unavailable_after_failures=self.config.unavailable_after_failures,
            stale_after_seconds=self.config.stale_after_seconds,
        )

    def directory(self) -> Any:
        providers = self.capabilities.system_providers(SERVICE_DIRECTORY)
        return providers[0].provider if providers else None

    async def service_info(self, service_id: str) -> ServiceInfo | None:
        directory = self.directory()
        return await directory.service(service_id) if directory else None

    async def services(self) -> list[ServiceInfo]:
        directory = self.directory()
        return await directory.services() if directory else []

    async def active_maintenance(self, session: AsyncSession, service_id: str) -> MaintenanceWindow | None:
        return (
            await session.execute(
                select(MaintenanceWindow)
                .where(
                    MaintenanceWindow.status == "active",
                    or_(MaintenanceWindow.service_id == service_id, MaintenanceWindow.service_id.is_(None)),
                )
                .order_by(MaintenanceWindow.starts_at)
                .limit(1)
            )
        ).scalar_one_or_none()

    async def inputs(self, session: AsyncSession, service_id: str, now: datetime) -> tuple[Inputs, Any]:
        info = await self.service_info(service_id)
        samples = (
            (
                await session.execute(
                    select(HealthSample)
                    .where(HealthSample.service_id == service_id, HealthSample.checked_at <= now)
                    .order_by(HealthSample.checked_at.desc())
                    .limit(RECENT)
                )
            )
            .scalars()
            .all()
        )
        failures = 0
        for sample in samples:
            if sample.ok:
                break
            failures += 1
        maintenance = await self.active_maintenance(session, service_id)
        last = samples[0] if samples else None
        return (
            Inputs(
                now=now,
                connection_state=info.state if info else None,
                last_check_at=last.checked_at if last else None,
                last_ok=last.ok if last else None,
                last_latency_ms=last.latency_ms if last else None,
                consecutive_failures=failures,
                maintenance_active=maintenance is not None,
            ),
            maintenance,
        )

    async def evaluate(self, service_id: str, *, occurred_at: datetime | None = None) -> Derived:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            inputs, maintenance = await self.inputs(session, service_id, now)
            derived = derive(inputs, self.thresholds())
            row = await session.get(ServiceState, service_id, with_for_update=True)
            last_ok_at = inputs.last_check_at if inputs.last_ok else None
            if row is None:
                row = ServiceState(
                    service_id=service_id,
                    state=derived.state,
                    state_since=occurred_at or now,
                    state_seq=0,
                    reason=derived.reason,
                    rules_version=RULES_VERSION,
                )
                session.add(row)
                before: str | None = None
                changed = True
            else:
                before = row.state
                changed = row.state != derived.state
            row.last_check_at = inputs.last_check_at
            if last_ok_at is not None:
                row.last_ok_at = last_ok_at
            row.maintenance_id = maintenance.id if maintenance else None
            if not changed:
                row.reason = derived.reason
                return derived
            at = occurred_at or now
            row.state, row.reason, row.state_since = derived.state, derived.reason, at
            row.state_seq += 1
            row.rules_version = RULES_VERSION
            await session.flush()
            session.add(
                StateHistory(
                    service_id=service_id,
                    from_state=before,
                    to_state=derived.state,
                    occurred_at=at,
                    received_at=now,
                    reason=derived.reason,
                )
            )
            await self.events.publish(
                session,
                "service.status_changed",
                {
                    "service_id": service_id,
                    "dimension": "health",
                    "from_state": before,
                    "to_state": derived.state,
                    "state_seq": row.state_seq,
                    "reason": derived.reason,
                },
                occurred_at=at,
                actor=SYSTEM,
                subject=SubjectRef("service", service_id),
                source="health",
            )
            metrics.increment(f"health.state_changes.{metric_part(derived.state)}")
        return derived

    async def evaluate_all(self) -> int:
        """Re-derive every known service (sweeps, maintenance transitions, start-up)."""
        known = {info.id for info in await self.services()}
        async with self.database.session() as session:
            known |= set((await session.execute(select(ServiceState.service_id))).scalars())
        for service_id in sorted(known):
            await self.evaluate(service_id)
        return len(known)
