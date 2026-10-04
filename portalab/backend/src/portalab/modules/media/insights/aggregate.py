"""Daily aggregates (027): per day (UTC), member and kind — plays, completed plays, time spent and distinct
works — rebuilt only for the days the ingestion marked as changed. Statistics read these rows for totals
and timelines; rankings read the raw rows of the period."""

from datetime import timedelta

from sqlalchemy import ColumnElement, delete, func, literal, select
from sqlalchemy.dialects.postgresql import insert

from portalab.core.db import Database
from portalab.modules.media.models import Activity, ActivityDaily, ActivityDirtyDay

JOB = "media.activity_aggregate"
BATCH = 120
NIL = "00000000-0000-0000-0000-000000000000"
COMPLETED = 0.85


def completed_clause() -> ColumnElement[bool]:
    return (Activity.progress >= COMPLETED) | (
        Activity.progress.is_(None)
        & (Activity.duration_s > 0)
        & (Activity.watched_s >= Activity.duration_s * COMPLETED)
    )


class ActivityAggregator:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def run(self) -> int:
        """Rebuild a batch of changed days; returns how many were rebuilt."""
        async with self.database.unit_of_work() as uow:
            session = uow.session
            days = list(
                (
                    await session.execute(
                        select(ActivityDirtyDay.day)
                        .order_by(ActivityDirtyDay.day)
                        .limit(BATCH)
                        .with_for_update(skip_locked=True)
                    )
                ).scalars()
            )
            for day in days:
                await session.execute(delete(ActivityDaily).where(ActivityDaily.day == day))
                user_key = func.coalesce(Activity.user_id, literal(NIL).cast(Activity.user_id.type))
                work = func.coalesce(
                    func.cast(Activity.work_id, Activity.title.type), Activity.parent_title, Activity.title
                )
                rows = (
                    select(
                        literal(day).label("day"),
                        user_key.label("user_key"),
                        Activity.kind,
                        func.count().label("plays"),
                        func.count().filter(completed_clause()).label("completed"),
                        func.coalesce(func.sum(Activity.watched_s), 0.0).label("seconds"),
                        func.count(func.distinct(work)).label("works"),
                    )
                    .where(
                        Activity.counted.is_(True),
                        Activity.started_at >= day,
                        Activity.started_at < day + timedelta(days=1),
                    )
                    .group_by(user_key, Activity.kind)
                )
                await session.execute(
                    insert(ActivityDaily).from_select(
                        ["day", "user_key", "kind", "plays", "completed", "seconds", "works"], rows
                    )
                )
            if days:
                await session.execute(delete(ActivityDirtyDay).where(ActivityDirtyDay.day.in_(days)))
        return len(days)
