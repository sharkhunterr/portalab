"""Trends (T031; FR-026): hourly or daily rollups of a metric over a period, and the history of component
health changes — observability history, kept apart from users' functional data."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from portalab.core.db import Database
from portalab.modules.observability.models import HealthHistory, Rollup


async def trends(
    database: Database, *, metric: str, component: str | None, since: datetime, bucket: str
) -> dict[str, Any]:
    async with database.session() as session:
        statement = (
            select(
                Rollup.bucket,
                func.sum(Rollup.count),
                func.sum(Rollup.sum),
                func.max(Rollup.max),
                func.max(Rollup.p95),
            )
            .where(Rollup.metric == metric, Rollup.bucket_kind == bucket, Rollup.bucket >= since)
            .group_by(Rollup.bucket)
            .order_by(Rollup.bucket)
        )
        if component:
            statement = statement.where(Rollup.component == component)
        points = [
            {"bucket": at.isoformat(), "count": int(count), "sum": float(total), "max": peak, "p95": p95}
            for at, count, total, peak, p95 in (await session.execute(statement)).all()
        ]
        history_statement = (
            select(HealthHistory)
            .where(HealthHistory.occurred_at >= since)
            .order_by(HealthHistory.occurred_at)
        )
        if component:
            history_statement = history_statement.where(HealthHistory.component == component)
        changes = [
            {
                "component": h.component,
                "axis": h.axis,
                "from": h.from_state,
                "to": h.to_state,
                "occurred_at": h.occurred_at.isoformat(),
            }
            for h in (await session.execute(history_statement.limit(500))).scalars()
        ]
    return {"metric": metric, "bucket": bucket, "points": points, "health_changes": changes}
