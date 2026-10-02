"""Availability and downtime (T013; R6, FR-023..025).

Hourly rollups summarize raw samples (count, OK count, p95 latency) and the time spent ``unavailable``
according to the state history (``occurred_at``, not the time the portal learnt it). Hours without any
sample are reported as **gaps**, never as uptime.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.modules.health.models import HealthRollup, HealthSample, StateHistory

HOUR = timedelta(hours=1)


def hour_start(value: datetime) -> datetime:
    return value.replace(minute=0, second=0, microsecond=0)


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return ordered[index]


async def downtime_seconds(session: AsyncSession, service_id: str, start: datetime, end: datetime) -> int:
    """Seconds of ``[start, end)`` the service spent unavailable, from its state history."""
    before = (
        await session.execute(
            select(StateHistory.to_state)
            .where(StateHistory.service_id == service_id, StateHistory.occurred_at < start)
            .order_by(StateHistory.occurred_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    changes = (
        await session.execute(
            select(StateHistory.occurred_at, StateHistory.to_state)
            .where(
                StateHistory.service_id == service_id,
                StateHistory.occurred_at >= start,
                StateHistory.occurred_at < end,
            )
            .order_by(StateHistory.occurred_at)
        )
    ).all()
    total, cursor, state = 0.0, start, before
    for at, to_state in changes:
        if state == "unavailable":
            total += (at - cursor).total_seconds()
        cursor, state = at, to_state
    if state == "unavailable":
        total += (end - cursor).total_seconds()
    return int(total)


async def rollup_bucket(session: AsyncSession, service_id: str, bucket: datetime) -> HealthRollup | None:
    end = bucket + HOUR
    rows = (
        await session.execute(
            select(HealthSample.ok, HealthSample.latency_ms).where(
                HealthSample.service_id == service_id,
                HealthSample.checked_at >= bucket,
                HealthSample.checked_at < end,
            )
        )
    ).all()
    downtime = await downtime_seconds(session, service_id, bucket, end)
    values = {
        "service_id": service_id,
        "bucket_start": bucket,
        "samples": len(rows),
        "ok_samples": sum(1 for ok, _ in rows if ok),
        "p95_latency_ms": p95([latency for ok, latency in rows if ok and latency is not None]),
        "downtime_seconds": downtime,
    }
    await session.execute(
        insert(HealthRollup)
        .values(**values)
        .on_conflict_do_update(constraint="uq_health_rollups_bucket", set_=values)
    )
    return None


@dataclass(frozen=True, slots=True)
class Availability:
    samples: int
    ok_samples: int
    downtime_seconds: int
    gap_hours: int

    @property
    def ratio(self) -> float | None:
        return self.ok_samples / self.samples if self.samples else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "availability": self.ratio,
            "samples": self.samples,
            "ok_samples": self.ok_samples,
            "downtime_seconds": self.downtime_seconds,
            "gap_hours": self.gap_hours,
        }


async def availability(
    session: AsyncSession, service_id: str, start: datetime, end: datetime
) -> Availability:
    """Availability over ``[start, end)``: complete hours from rollups, the current hour from raw samples."""
    current = hour_start(end)
    rollups = (
        (
            await session.execute(
                select(HealthRollup).where(
                    HealthRollup.service_id == service_id,
                    HealthRollup.bucket_start >= start,
                    HealthRollup.bucket_start < current,
                )
            )
        )
        .scalars()
        .all()
    )
    samples = sum(r.samples for r in rollups)
    ok = sum(r.ok_samples for r in rollups)
    downtime = sum(r.downtime_seconds for r in rollups)
    hours = int((current - hour_start(start)).total_seconds() // 3600)
    gaps = hours - sum(1 for r in rollups if r.samples)
    live = (
        await session.execute(
            select(func.count(), func.count().filter(HealthSample.ok)).where(
                HealthSample.service_id == service_id,
                HealthSample.checked_at >= max(current, start),
                HealthSample.checked_at <= end,
            )
        )
    ).one()
    return Availability(samples + int(live[0]), ok + int(live[1]), downtime, max(gaps, 0))
