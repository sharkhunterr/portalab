"""Time triggers (T021; R2): one-time ``at``, ``recurring`` daily / weekly / monthly at HH:MM in a time zone
(DST: a missing wall time moves forward, a repeated one takes the earlier instant) — **no cron strings** —
and pending ``relative`` fires. A due fire is claimed once (row lock) and goes through the same Gate and
Runner as events."""

from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.automations.definitions.schema import Trigger
from portalab.modules.automations.models import PendingFire, ScheduleState
from portalab.modules.automations.observability import log, metrics
from portalab.modules.automations.triggers.consumer import Triggers


def wall_clock(local: datetime, zone: ZoneInfo) -> datetime:
    naive = local.replace(tzinfo=None)
    early, late = naive.replace(tzinfo=zone, fold=0), naive.replace(tzinfo=zone, fold=1)
    if (
        early.utcoffset() != late.utcoffset()
        and early.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive
    ):
        shift = abs((late.utcoffset() or timedelta(0)) - (early.utcoffset() or timedelta(0)))
        return (naive + shift).replace(tzinfo=zone).astimezone(UTC)
    return early.astimezone(UTC)


def next_fire(trigger: Trigger, after: datetime) -> datetime | None:
    """The first fire strictly after ``after`` (deterministic)."""
    if trigger.kind == "at":
        return trigger.at if trigger.at and trigger.at > after else None
    if trigger.kind != "recurring" or trigger.schedule is None:
        return None
    try:
        zone = ZoneInfo(trigger.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    schedule = trigger.schedule
    at_time = time.fromisoformat(schedule.time)
    day = after.astimezone(zone).date()
    for offset in range(0, 400):
        candidate = day + timedelta(days=offset)
        if schedule.frequency == "weekly" and candidate.weekday() != schedule.weekday:
            continue
        if schedule.frequency == "monthly" and candidate.day != schedule.day:
            continue
        moment = wall_clock(datetime.combine(candidate, at_time), zone)
        if moment > after:
            return moment
    return None


class Scheduler:
    def __init__(self, database: Database, triggers: Triggers, *, clock: Clock | None = None) -> None:
        self.database = database
        self.triggers = triggers
        self.clock = clock

    async def run(self, now: datetime | None = None) -> int:
        now = now or utc_now(self.clock)
        fired = 0
        for item in await self.triggers.live():
            trigger = item.definition.trigger
            if trigger.kind not in ("at", "recurring"):
                continue
            due: datetime | None = None
            async with self.database.unit_of_work() as uow:
                state = await uow.session.get(ScheduleState, item.id, with_for_update=True)
                if state is None:
                    state = ScheduleState(
                        automation_id=item.id, next_fire_at=next_fire(trigger, now - timedelta(seconds=1))
                    )
                    uow.session.add(state)
                elif state.next_fire_at is None and state.last_fired_at is None:
                    state.next_fire_at = next_fire(trigger, now - timedelta(seconds=1))
                if state.next_fire_at is not None and state.next_fire_at <= now:
                    due = state.next_fire_at
                    state.last_fired_at = due
                    state.next_fire_at = next_fire(trigger, due)
                    if (now - due) > timedelta(minutes=5):
                        metrics.increment("automations.scheduler.late")
            if due is not None:
                await self._fire(item, {"type": "schedule", "fire_at": due.isoformat()})
                fired += 1
        async with self.database.unit_of_work() as uow:
            pending = list(
                (
                    await uow.session.execute(
                        select(PendingFire)
                        .where(PendingFire.fired.is_(False), PendingFire.fire_at <= now)
                        .with_for_update(skip_locked=True)
                        .limit(200)
                    )
                ).scalars()
            )
            for row in pending:
                row.fired = True
            due_relative = [(row.automation_id, row.source_event_id, row.fire_at) for row in pending]
        live = {item.id: item for item in await self.triggers.live()}
        for automation_id, source, fire_at in due_relative:
            if automation_id in live:
                await self._fire(
                    live[automation_id],
                    {"type": "relative", "source_event": str(source), "fire_at": fire_at.isoformat()},
                )
                fired += 1
        return fired

    async def _fire(self, item: Any, ref: dict[str, Any]) -> None:
        try:
            await self.triggers.fire(item, None, ref=ref)
        except Exception:
            log.exception("scheduled automation failed", extra={"fields": {"automation": item.key}})
