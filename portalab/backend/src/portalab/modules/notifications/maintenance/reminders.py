"""Maintenance reminders (T021; R9): a fixed system source driven by 006 ``maintenance.*`` events.

* ``scheduled`` / ``rescheduled`` (schedule version v): reminders J-1 and H-1 are stored (unique per
  ``(maintenance, version, kind)``) and queued at their ``run_at``; earlier versions' pending reminders are
  cancelled and people already notified receive a corrective message;
* ``started``: an immediate alert; ``cancelled``: pending reminders cancelled + corrective;
* a reminder evaluated after the maintenance start (``valid_until``) is ``expired``, never sent late;
* replays never produce anything (system effects are skipped during reconstruction) and every
  communication is deduplicated.
Audience: holders of ``services.read`` (permission re-checked per recipient)."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.capabilities.notifications import CommunicationRef, CommunicationRequest, WithPermission
from portalab.core.db import Database
from portalab.core.jobs.queue import enqueue
from portalab.core.time import Clock, utc_now
from portalab.modules.notifications.models import MaintenanceReminder

CATEGORY = "system.maintenance"
JOB = "notifications.maintenance_reminder"
CONSUMER = "notifications.maintenance"
OWNER = "module:notifications"
OFFSETS = {"j1": timedelta(days=1), "h1": timedelta(hours=1)}

Send = Callable[[CommunicationRequest], Awaitable[CommunicationRef]]


def _request(
    kind: str, payload: dict[str, Any], version: int, *, alert: bool = False
) -> CommunicationRequest:
    maintenance = str(payload["maintenance_id"])
    return CommunicationRequest(
        category=CATEGORY,
        template_key=f"notifications:maintenance.{kind}",
        audience=WithPermission(
            "services.read", (str(payload["service_id"]),) if payload.get("service_id") else ()
        ),
        dedup_key=f"maintenance:{maintenance}:v{version}:{kind}",
        kind="alert" if alert else "notification",
        priority="high",
        params={
            "starts_at": str(payload.get("starts_at", "")),
            "ends_at": str(payload.get("ends_at", "")),
            # issue 398: which maintenance, and what its window says
            "title": str(payload.get("title") or "")[:160] or "none",
            "quote": str(payload.get("description") or "")[:500],
        },
        source="system",
        source_ref=f"maintenance:{maintenance}",
        subject_ref=f"maintenance:{maintenance}",
        required_permission="services.read",
        valid_until=datetime.fromisoformat(str(payload["starts_at"])) if kind in ("j1", "h1") else None,
        action_url=f"/services/{payload['service_id']}" if payload.get("service_id") else "/services",
    )


class MaintenanceReminders:
    def __init__(self, database: Database, send: Send, *, clock: Clock | None = None) -> None:
        self.database = database
        self.send = send
        self.clock = clock

    def consumer(self) -> Consumer:
        async def handle(envelope: Envelope, ctx: ConsumerContext) -> None:
            if ctx.replay:
                return  # reconstruction never notifies anyone
            await self.on_event(envelope.type, dict(envelope.payload))

        types = frozenset(
            f"maintenance.{t}" for t in ("scheduled", "rescheduled", "started", "ended", "cancelled")
        )
        return Consumer(CONSUMER, types, handle, OWNER, replay_safe=False)

    async def on_event(self, event_type: str, payload: dict[str, Any]) -> None:
        maintenance = str(payload["maintenance_id"])
        version = int(payload.get("schedule_version", 1))
        if event_type in ("maintenance.scheduled", "maintenance.rescheduled"):
            await self._supersede(maintenance, version, payload)
            await self._schedule(maintenance, version, payload)
        elif event_type == "maintenance.cancelled":
            await self._supersede(maintenance, version + 1, payload, cancelled=True)
        elif event_type == "maintenance.started":
            await self.send(_request("start", payload, version, alert=True))

    async def _supersede(
        self, maintenance: str, version: int, payload: dict[str, Any], *, cancelled: bool = False
    ) -> None:
        now = utc_now(self.clock)
        notified = False
        async with self.database.unit_of_work() as uow:
            rows = (
                (
                    await uow.session.execute(
                        select(MaintenanceReminder)
                        .where(
                            MaintenanceReminder.maintenance_id == maintenance,
                            MaintenanceReminder.schedule_version < version,
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                if row.status == "sent":
                    notified = True
                elif row.status == "scheduled":
                    row.status, row.updated_at = "cancelled", now
        if notified:
            kind = "cancelled" if cancelled else "rescheduled"
            await self.send(_request(kind, payload, version, alert=False))

    async def _schedule(self, maintenance: str, version: int, payload: dict[str, Any]) -> None:
        starts = datetime.fromisoformat(str(payload["starts_at"]))
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            for kind, offset in OFFSETS.items():
                run_at = starts - offset
                inserted = (
                    await uow.session.execute(
                        insert(MaintenanceReminder)
                        .values(
                            maintenance_id=maintenance,
                            schedule_version=version,
                            kind=kind,
                            service_id=str(payload["service_id"]) if payload.get("service_id") else None,
                            run_at=run_at,
                            valid_until=starts,
                            status="scheduled",
                            updated_at=now,
                        )
                        .on_conflict_do_nothing(constraint="uq_maintenance_reminders")
                        .returning(MaintenanceReminder.id)
                    )
                ).scalar_one_or_none()
                if inserted is not None:
                    await enqueue(
                        uow.session,
                        kind=JOB,
                        payload={
                            "reminder": str(inserted),
                            "starts_at": payload["starts_at"],
                            "ends_at": payload["ends_at"],
                            "title": str(payload.get("title") or "")[:160],
                            "description": str(payload.get("description") or "")[:500],
                        },
                        dedup_key=f"{JOB}:{maintenance}:v{version}:{kind}",
                        run_at=max(run_at, now),
                        clock=self.clock,
                    )

    async def run(self, payload: dict[str, Any]) -> str:
        """Job handler: send the reminder unless cancelled or expired. Returns its final status."""
        reminder_id = UUID(str(payload["reminder"]))
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(MaintenanceReminder, reminder_id, with_for_update=True)
            if row is None or row.status != "scheduled":
                return row.status if row else "missing"
            if now >= row.valid_until:
                row.status, row.updated_at = "expired", now
                return "expired"
            details = {
                "maintenance_id": row.maintenance_id,
                "service_id": row.service_id,
                "starts_at": payload.get("starts_at", row.valid_until.isoformat()),
                "ends_at": payload.get("ends_at", ""),
                "title": payload.get("title", ""),
                "description": payload.get("description", ""),
            }
            kind, version = row.kind, row.schedule_version
        ref = await self.send(_request(kind, details, version))
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(MaintenanceReminder, reminder_id, with_for_update=True)
            if row is not None and row.status == "scheduled":
                row.status, row.communication_id, row.updated_at = "sent", ref.id, utc_now(self.clock)
        return "sent"
