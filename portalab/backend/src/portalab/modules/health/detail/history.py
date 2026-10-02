"""Health history (T014; FR-023..025): state transitions by ``occurred_at``, hourly availability buckets
with gaps marked, and — for ``infrastructure.read`` — metric series. Distinct from incidents (Support)
and sync history (Connectors)."""

from datetime import datetime
from typing import Any

from sqlalchemy import select

from portalab.modules.health.models import HealthRollup, InfraSample, RecentError, StateHistory
from portalab.modules.health.rollups.availability import HOUR, hour_start
from portalab.modules.health.state.service import StateService


class HistoryQuery:
    def __init__(self, state: StateService) -> None:
        self.state = state

    async def history(
        self, service_id: str, start: datetime, end: datetime, *, with_metrics: bool = False
    ) -> dict[str, Any]:
        async with self.state.database.session() as session:
            transitions = (
                (
                    await session.execute(
                        select(StateHistory)
                        .where(
                            StateHistory.service_id == service_id,
                            StateHistory.occurred_at >= start,
                            StateHistory.occurred_at < end,
                        )
                        .order_by(StateHistory.occurred_at)
                    )
                )
                .scalars()
                .all()
            )
            rollups = {
                r.bucket_start: r
                for r in (
                    await session.execute(
                        select(HealthRollup).where(
                            HealthRollup.service_id == service_id,
                            HealthRollup.bucket_start >= hour_start(start),
                            HealthRollup.bucket_start < end,
                        )
                    )
                ).scalars()
            }
            buckets: list[dict[str, Any]] = []
            bucket = hour_start(start)
            while bucket < end and len(buckets) < 24 * 93:
                row = rollups.get(bucket)
                if row is None or row.samples == 0:
                    buckets.append({"start": bucket.isoformat(), "gap": True})
                else:
                    buckets.append(
                        {
                            "start": bucket.isoformat(),
                            "gap": False,
                            "availability": row.ok_samples / row.samples,
                            "downtime_seconds": row.downtime_seconds,
                        }
                    )
                bucket += HOUR
            result: dict[str, Any] = {
                "transitions": [
                    {
                        "from": t.from_state,
                        "to": t.to_state,
                        "occurred_at": t.occurred_at.isoformat(),
                        "reason": t.reason,
                    }
                    for t in transitions
                ],
                "buckets": buckets,
            }
            if with_metrics:
                samples = (
                    await session.execute(
                        select(InfraSample)
                        .where(
                            InfraSample.service_id == service_id,
                            InfraSample.sampled_at >= start,
                            InfraSample.sampled_at < end,
                        )
                        .order_by(InfraSample.sampled_at)
                    )
                ).scalars()
                series: dict[str, list[dict[str, Any]]] = {}
                for s in samples:
                    series.setdefault(s.metric, []).append(
                        {
                            "at": s.sampled_at.isoformat(),
                            "value": s.value if s.available else None,
                            "available": s.available,
                        }
                    )
                result["metrics"] = series
        return result

    async def recent_errors(self, service_id: str, limit: int = 20) -> list[dict[str, Any]]:
        async with self.state.database.session() as session:
            rows = (
                await session.execute(
                    select(RecentError)
                    .where(RecentError.service_id == service_id)
                    .order_by(RecentError.last_seen_at.desc())
                    .limit(limit)
                )
            ).scalars()
            return [
                {
                    "code": r.code,
                    "message": r.message,
                    "count": r.count,
                    "first_seen_at": r.occurred_at.isoformat(),
                    "last_seen_at": r.last_seen_at.isoformat(),
                }
                for r in rows
            ]
