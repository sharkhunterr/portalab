"""Performance attribution (T021; R7, FR-013/014): per route/component, how long requests and jobs spent
in each phase (``portal_wait``, ``external_wait``, ``internal``, ``timeout``) and which phase dominates.
"Slow" uses the configured ``observability.thresholds.performance.slowMs`` — no threshold in code."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from portalab.core.db import Database
from portalab.modules.observability.models import MetricSample

TIMED = ("http.request", "job.run", "sync.duration")


async def performance(
    database: Database, since: datetime, *, slow_ms: int, limit: int = 50
) -> list[dict[str, Any]]:
    async with database.session() as session:
        rows = (
            (
                await session.execute(
                    select(MetricSample).where(
                        MetricSample.kind == "histogram",
                        MetricSample.metric.in_(TIMED),
                        MetricSample.sampled_at >= since,
                    )
                )
            )
            .scalars()
            .all()
        )
    groups: dict[tuple[str, str, str], dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {"count": 0.0, "sum": 0.0, "max": 0.0})
    )
    for row in rows:
        labels = {k: v for k, v in row.labels.items() if k not in ("phase", "status")}
        target = (
            labels.get("route") or labels.get("kind") or labels.get("service") or labels.get("method") or ""
        )
        phase = str(row.labels.get("phase", "internal"))
        bucket = groups[(row.component, row.metric, target)][phase]
        bucket["count"] += row.count
        bucket["sum"] += row.sum
        bucket["max"] = max(bucket["max"], row.max or 0.0)
    views: list[dict[str, Any]] = []
    for (component, metric, target), phases in groups.items():
        calls = max((p["count"] for p in phases.values()), default=0.0)
        if not calls:
            continue
        total = sum(p["sum"] for p in phases.values())
        average = total / calls
        dominant = max(phases.items(), key=lambda item: item[1]["sum"])[0]
        views.append(
            {
                "component": component,
                "metric": metric,
                "target": target,
                "calls": int(calls),
                "average_ms": round(average, 1),
                "max_ms": round(max(p["max"] for p in phases.values()), 1),
                "timeouts": int(phases.get("timeout", {}).get("count", 0)),
                "phases": {name: round(p["sum"] / calls, 1) for name, p in phases.items()},
                "dominant_phase": dominant,
                "slow": average > slow_ms,
            }
        )
    views.sort(key=lambda v: (not v["slow"], -float(v["average_ms"])))
    return views[:limit]


def window(hours: int, now: datetime) -> datetime:
    return now - timedelta(hours=max(1, min(hours, 24 * 31)))
