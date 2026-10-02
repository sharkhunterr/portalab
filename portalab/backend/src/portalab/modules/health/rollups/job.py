"""Hourly rollup job (T013): rolls every complete hour since the last rollup of each service (catching up
after downtime), then lets the 021 retention engine prune samples and old rollups."""

from datetime import datetime, timedelta

from sqlalchemy import func, select

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.health.models import HealthRollup, HealthSample
from portalab.modules.health.observability import metrics
from portalab.modules.health.rollups.availability import HOUR, hour_start, rollup_bucket

MAX_CATCH_UP = timedelta(days=7)


class RollupJob:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def run(self, now: datetime | None = None) -> int:
        now = now or utc_now(self.clock)
        last_complete = hour_start(now)
        rolled = 0
        async with self.database.unit_of_work() as uow:
            session = uow.session
            services = (
                await session.execute(
                    select(HealthSample.service_id, func.min(HealthSample.checked_at)).group_by(
                        HealthSample.service_id
                    )
                )
            ).all()
            for service_id, first_sample in services:
                latest = await session.scalar(
                    select(func.max(HealthRollup.bucket_start)).where(HealthRollup.service_id == service_id)
                )
                bucket = latest + HOUR if latest else hour_start(first_sample)
                bucket = max(bucket, last_complete - MAX_CATCH_UP)
                while bucket < last_complete:
                    await rollup_bucket(session, service_id, bucket)
                    bucket += HOUR
                    rolled += 1
        metrics.gauge("health.rollup_lag_seconds", (now - last_complete).total_seconds())
        return rolled
