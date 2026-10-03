"""``ReminderService`` (T027; R13): user-initiated reminders on calendar items, fired by a job through the
``notifications.send`` port (category ``calendar.reminder``). At fire time the item is fetched again **as
the user** from its source: gone or no longer visible ⇒ ``cancelled``; moved to a later time ⇒ the
reminder is rescheduled (and the user told it changed); otherwise it is sent once (dedup per reminder)."""

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from portalab.capabilities.content import CalendarItem, CalendarSourceRegistry
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.jobs.queue import enqueue
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.calendar.models import Reminder
from portalab.modules.calendar.settings import CalendarConfig

JOB = "calendar.reminder"
log = get_logger("portalab.calendar")


class ReminderNotFound(NotFound):
    default_code = "calendar.reminder_not_found"
    default_title = "Reminder not found"


def snapshot(item: CalendarItem) -> str:
    raw = f"{item.title}|{item.starts_at.isoformat() if item.starts_at else item.date}|{item.status}"
    return hashlib.sha256(raw.encode()).hexdigest()


def start_of(item: CalendarItem) -> datetime | None:
    if item.starts_at is not None:
        return item.starts_at
    if item.date is not None:
        from datetime import UTC

        return datetime.combine(item.date, datetime.min.time(), tzinfo=UTC)
    return None


@dataclass(frozen=True, slots=True)
class ReminderView:
    id: UUID
    source_kind: str
    source_id: str
    lead_minutes: int
    remind_at: datetime
    status: str
    title: str


def _view(row: Reminder) -> ReminderView:
    return ReminderView(
        row.id, row.source_kind, row.source_id, row.lead_minutes, row.remind_at, row.status, row.title
    )


class ReminderService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        sources: CalendarSourceRegistry,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.sources = sources
        self.config = config  # callable → CalendarConfig
        self.clock = clock

    async def _item(self, kind: str, source_id: str, user: UUID) -> CalendarItem | None:
        source = self.sources.get(kind)
        if source is None:
            return None
        try:
            return await asyncio.wait_for(source.item(source_id, Principal(user_id=user)), timeout=5)
        except Exception:
            return None

    async def create(self, user: UUID, kind: str, source_id: str, lead_minutes: int) -> ReminderView:
        config: CalendarConfig = self.config()
        if lead_minutes not in config.reminder_lead_options:
            raise ValidationFailed("Choose one of the offered reminder times.", code="calendar.invalid_lead")
        item = await self._item(kind, source_id, user)
        start = start_of(item) if item is not None else None
        if item is None or start is None:
            raise ReminderNotFound("This item does not exist.")
        now = utc_now(self.clock)
        remind_at = start - timedelta(minutes=lead_minutes)
        if remind_at <= now:
            raise ValidationFailed("This reminder time has already passed.", code="calendar.reminder_past")
        try:
            async with self.database.unit_of_work() as uow:
                row = Reminder(
                    user_id=user,
                    source_kind=kind,
                    source_id=source_id,
                    lead_minutes=lead_minutes,
                    remind_at=remind_at,
                    status="scheduled",
                    title=item.title[:200],
                    last_snapshot_hash=snapshot(item),
                    created_at=now,
                    updated_at=now,
                )
                uow.session.add(row)
                await uow.session.flush()
                await self._enqueue(uow.session, row)
                return _view(row)
        except IntegrityError as exc:
            raise Conflict("You already have this reminder.", code="calendar.reminder_exists") from exc

    async def _enqueue(self, session: Any, row: Reminder) -> None:
        await enqueue(
            session,
            kind=JOB,
            payload={"reminder": str(row.id)},
            dedup_key=f"{JOB}:{row.id}:{row.remind_at.isoformat()}",
            run_at=row.remind_at,
            clock=self.clock,
        )

    async def mine(self, user: UUID) -> list[ReminderView]:
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(Reminder).where(Reminder.user_id == user).order_by(Reminder.remind_at)
                    )
                )
                .scalars()
                .all()
            )
        return [_view(r) for r in rows]

    async def remove(self, user: UUID, reminder_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(
                delete(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user)
            )
            if not getattr(result, "rowcount", 0):
                raise ReminderNotFound("This reminder does not exist.")

    async def fire(self, payload: dict[str, Any]) -> str:
        """Job handler; returns the outcome (``sent``, ``updated``, ``cancelled`` or a no-op state)."""
        reminder_id = UUID(str(payload["reminder"]))
        async with self.database.session() as session:
            row = await session.get(Reminder, reminder_id)
        if row is None or row.status != "scheduled":
            return row.status if row is not None else "missing"
        now = utc_now(self.clock)
        if row.remind_at > now:
            return "early"
        item = await self._item(row.source_kind, row.source_id, row.user_id)
        start = start_of(item) if item is not None else None
        if item is None or start is None or item.status in ("cancelled", "deleted"):
            await self._finish(row.id, "cancelled")
            await self._send(row, "calendar:notify.cancelled", {"title": row.title}, "cancelled")
            return "cancelled"
        new_at = start - timedelta(minutes=row.lead_minutes)
        if snapshot(item) != row.last_snapshot_hash and new_at > now:
            async with self.database.unit_of_work() as uow:
                current = await uow.session.get(Reminder, row.id, with_for_update=True)
                if current is None or current.status != "scheduled":
                    return "missing"
                current.remind_at, current.title = new_at, item.title[:200]
                current.last_snapshot_hash, current.updated_at = snapshot(item), now
                await self._enqueue(uow.session, current)
            await self._send(
                row,
                "calendar:notify.updated",
                {"title": item.title[:200], "starts_at": start.isoformat()},
                "updated",
            )
            return "updated"
        await self._finish(row.id, "sent")
        await self._send(
            row,
            "calendar:notify.reminder",
            {"title": item.title[:200], "starts_at": start.isoformat()},
            "sent",
        )
        async with self.database.unit_of_work() as uow:
            await self.events.publish(
                uow.session,
                "calendar.reminder_sent",
                {"reminder": str(row.id), "source": row.source_kind},
                occurred_at=now,
                subject=SubjectRef("user", str(row.user_id)),
                source="calendar",
                dedup_key=f"calendar.reminder_sent:{row.id}",
            )
        return "sent"

    async def _finish(self, reminder_id: UUID, status: str) -> None:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Reminder, reminder_id, with_for_update=True)
            if row is not None and row.status == "scheduled":
                row.status, row.updated_at = status, utc_now(self.clock)

    async def _send(self, row: Reminder, template: str, params: dict[str, Any], outcome: str) -> None:
        try:
            providers = self.capabilities.system_providers(NOTIFY)
        except Exception:
            return
        if not providers:
            return
        try:
            await asyncio.wait_for(
                providers[0].provider.send(
                    CommunicationRequest(
                        category="calendar.reminder",
                        template_key=template,
                        audience=Users((row.user_id,)),
                        dedup_key=f"calendar.reminder:{row.id}:{outcome}:{row.remind_at.isoformat()}",
                        params=params,
                        source="module",
                        subject_ref=f"calendar:{row.source_kind}:{row.source_id}",
                        action_url="/calendar",
                    )
                ),
                timeout=10,
            )
        except Exception:
            log.warning("calendar reminder notification not sent")

    async def erase(self, user: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(delete(Reminder).where(Reminder.user_id == user))
