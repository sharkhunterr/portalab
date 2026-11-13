"""Maintenance windows (T016; R4, CD-020, FR-032/033).

Windows are scheduled by **absolute instants** (UTC); when the operator meant a wall-clock time, the
reference time zone is stored alongside for display. Jobs ``health.maintenance_start`` /
``health.maintenance_end`` flip the window (and so the derived service state) at those instants; each job
carries the ``schedule_version`` it was planned for, so a rescheduled window ignores stale jobs. Missed
transitions (worker down) are reconciled at start-up and by every probe sweep. Events
``maintenance.scheduled|rescheduled|started|ended|cancelled`` carry ``schedule_version`` (reminders 010,
calendar 011). Cancelling is sensitive and audited.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.event_port import SubjectRef
from portalab.core.jobs.queue import enqueue
from portalab.core.time import require_aware, utc_now
from portalab.modules.health.common import InvalidWindow, MaintenanceNotFound, audit
from portalab.modules.health.models import MaintenanceWindow
from portalab.modules.health.state.service import SYSTEM, StateService

START_JOB = "health.maintenance_start"
END_JOB = "health.maintenance_end"


def window_out(row: MaintenanceWindow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "service_id": row.service_id,
        "title": row.title,
        "description": row.description,
        "starts_at": row.starts_at.isoformat(),
        "ends_at": row.ends_at.isoformat(),
        "reference_time_zone": row.reference_time_zone,
        "status": row.status,
        "schedule_version": row.schedule_version,
        "banner": row.banner,
    }


class MaintenanceService:
    def __init__(self, state: StateService, audit_sink: AuditSink) -> None:
        self.state = state
        self.audit = audit_sink

    @property
    def database(self) -> Any:
        return self.state.database

    def _validate(
        self, starts_at: datetime, ends_at: datetime, zone: str | None
    ) -> tuple[datetime, datetime]:
        try:
            starts, ends = require_aware(starts_at), require_aware(ends_at)
        except ValueError as exc:
            raise InvalidWindow("Maintenance instants must carry a time zone offset.") from exc
        if ends <= starts:
            raise InvalidWindow("A maintenance window must end after it starts.")
        if zone is not None:
            try:
                ZoneInfo(zone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise InvalidWindow("Unknown reference time zone.") from exc
        return starts, ends

    async def _publish(
        self, session: AsyncSession, row: MaintenanceWindow, transition: str, actor: Principal
    ) -> Any:
        return await self.state.events.publish(
            session,
            f"maintenance.{transition}",
            {
                "maintenance_id": str(row.id),
                "service_id": row.service_id,
                "starts_at": row.starts_at.isoformat(),
                "ends_at": row.ends_at.isoformat(),
                "schedule_version": row.schedule_version,
                "transition": transition,
                "reference_time_zone": row.reference_time_zone,
                "title": row.title,
                "description": (row.description or "")[:500],
            },
            occurred_at=utc_now(self.state.clock),
            actor=actor,
            subject=SubjectRef("maintenance", str(row.id)),
            source="health",
        )

    async def _schedule_jobs(self, session: AsyncSession, row: MaintenanceWindow) -> None:
        for kind, at in ((START_JOB, row.starts_at), (END_JOB, row.ends_at)):
            await enqueue(
                session,
                kind=kind,
                payload={"maintenance_id": str(row.id), "schedule_version": row.schedule_version},
                dedup_key=f"{kind}:{row.id}:v{row.schedule_version}",
                run_at=at,
                clock=self.state.clock,
            )

    async def create(
        self,
        actor: Principal,
        *,
        service_id: str | None,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        description: str = "",
        reference_time_zone: str | None = None,
        banner: bool = False,
    ) -> dict[str, Any]:
        starts, ends = self._validate(starts_at, ends_at, reference_time_zone)
        async with self.database.unit_of_work() as uow:
            row = MaintenanceWindow(
                service_id=service_id,
                title=title,
                description=description,
                starts_at=starts,
                ends_at=ends,
                reference_time_zone=reference_time_zone,
                banner=banner,
                status="scheduled",
                schedule_version=1,
                created_by=actor.user_id,
                created_at=utc_now(self.state.clock),
            )
            uow.session.add(row)
            await uow.session.flush()
            await self._schedule_jobs(uow.session, row)
            result = await self._publish(uow.session, row, "scheduled", actor)
            await audit(
                self.audit,
                uow.session,
                "maintenance.scheduled",
                actor,
                resource=ResourceRef("maintenance", str(row.id)),
                sensitive=False,
                event_id=result.event_id,
            )
            out = window_out(row)
        await self.reconcile()
        return out

    async def _row(self, session: AsyncSession, window_id: UUID) -> MaintenanceWindow:
        row = await session.get(MaintenanceWindow, window_id, with_for_update=True)
        if row is None:
            raise MaintenanceNotFound("No such maintenance window.")
        return row

    async def reschedule(
        self,
        actor: Principal,
        window_id: UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        reference_time_zone: str | None = None,
        banner: bool | None = None,
    ) -> dict[str, Any]:
        async with self.database.unit_of_work() as uow:
            row = await self._row(uow.session, window_id)
            if row.status in ("ended", "cancelled"):
                raise InvalidWindow("This maintenance window is over.")
            if banner is not None:
                row.banner = banner
            if title is not None:
                row.title = title
            if description is not None:
                row.description = description
            moved = starts_at is not None or ends_at is not None or reference_time_zone is not None
            if moved:
                starts, ends = self._validate(
                    starts_at or row.starts_at,
                    ends_at or row.ends_at,
                    reference_time_zone or row.reference_time_zone,
                )
                if row.status == "active" and starts != row.starts_at:
                    raise InvalidWindow("An active window can only change its end.")
                row.starts_at, row.ends_at = starts, ends
                if reference_time_zone is not None:
                    row.reference_time_zone = reference_time_zone
                row.schedule_version += 1
                await uow.session.flush()
                await self._schedule_jobs(uow.session, row)
                await self._publish(uow.session, row, "rescheduled", actor)
            out = window_out(row)
        await self.reconcile()
        return out

    async def cancel(self, actor: Principal, window_id: UUID) -> dict[str, Any]:
        async with self.database.unit_of_work() as uow:
            row = await self._row(uow.session, window_id)
            if row.status in ("ended", "cancelled"):
                raise InvalidWindow("This maintenance window is over.")
            row.status, row.cancelled_at = "cancelled", utc_now(self.state.clock)
            row.schedule_version += 1
            await uow.session.flush()
            result = await self._publish(uow.session, row, "cancelled", actor)
            await audit(
                self.audit,
                uow.session,
                "maintenance.cancelled",
                actor,
                resource=ResourceRef("maintenance", str(row.id)),
                sensitive=True,
                event_id=result.event_id,
            )
            out, affected = window_out(row), row.service_id
        await self._reevaluate(affected)
        return out

    async def windows(
        self, *, service_id: str | None = None, include_past: bool = False
    ) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            statement = select(MaintenanceWindow).order_by(MaintenanceWindow.starts_at)
            if service_id is not None:
                statement = statement.where(
                    or_(MaintenanceWindow.service_id == service_id, MaintenanceWindow.service_id.is_(None))
                )
            if not include_past:
                statement = statement.where(MaintenanceWindow.status.in_(("scheduled", "active")))
            return [window_out(row) for row in (await session.execute(statement)).scalars()]

    async def _reevaluate(self, service_id: str | None) -> None:
        if service_id is None:
            await self.state.evaluate_all()
        else:
            await self.state.evaluate(service_id)

    async def handle_job(self, payload: dict[str, Any], transition: str) -> None:
        async with self.database.session() as session:
            row = await session.get(MaintenanceWindow, UUID(payload["maintenance_id"]))
            if row is None or row.schedule_version != int(payload["schedule_version"]):
                return  # rescheduled or cancelled since this job was planned
        await self.reconcile()

    async def reconcile(self, now: datetime | None = None) -> list[str]:
        """Bring every window in line with the clock (start-up, sweeps, jobs); returns transitions made."""
        now = now or utc_now(self.state.clock)
        transitions: list[str] = []
        affected: set[str | None] = set()
        async with self.database.unit_of_work() as uow:
            rows: Sequence[MaintenanceWindow] = (
                (
                    await uow.session.execute(
                        select(MaintenanceWindow)
                        .where(MaintenanceWindow.status.in_(("scheduled", "active")))
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                if row.status == "scheduled" and row.starts_at <= now:
                    row.status = "active"
                    await self._publish(uow.session, row, "started", SYSTEM)
                    transitions.append(f"{row.id}:started")
                    affected.add(row.service_id)
                if row.status == "active" and row.ends_at <= now:
                    row.status = "ended"
                    await self._publish(uow.session, row, "ended", SYSTEM)
                    transitions.append(f"{row.id}:ended")
                    affected.add(row.service_id)
        for service_id in affected:
            await self._reevaluate(service_id)
        return transitions
