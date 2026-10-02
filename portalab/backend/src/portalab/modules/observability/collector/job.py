"""Collector (T008; R2, R8): drains the in-process hook queue into the observability store.

Counters and histograms are aggregated per ``(component, metric, labels, minute)`` into
``obs.metric_samples``; error observations go to the :class:`ErrorRecorder`. Complete hours/days are
rolled up into ``obs.rollups`` (the trends source). The collector is **fail-open**: when the store is
down the drained batch is dropped and counted — requests and jobs never wait on it.
"""

import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.metrics import MetricsRegistry, Observation, default_metrics
from portalab.core.time import Clock, utc_now
from portalab.modules.observability.errors.recorder import ErrorRecorder, fingerprint
from portalab.modules.observability.models import MetricSample, Rollup
from portalab.modules.observability.observability import log

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


def labels_key(labels: dict[str, Any]) -> str:
    return json.dumps(labels, sort_keys=True, separators=(",", ":"))[:512]


def p95(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))]


@dataclass
class _Bucket:
    kind: str
    values: list[float] = field(default_factory=list)


@dataclass
class CollectorStats:
    flushed: int = 0
    failures: int = 0
    dropped_batches: int = 0
    last_flush_at: datetime | None = None


class Collector:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        *,
        registry: MetricsRegistry = default_metrics,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.registry = registry
        self.recorder = ErrorRecorder(events)
        self.clock = clock
        self.stats = CollectorStats()

    async def flush(self) -> int:
        batch = self.registry.drain()
        if not batch:
            self.stats.last_flush_at = utc_now(self.clock)
            return 0
        try:
            await self._write(batch)
        except Exception:
            self.stats.failures += 1
            self.stats.dropped_batches += 1
            self.registry.dropped += len(batch)
            log.warning("observability flush failed; batch dropped", extra={"fields": {"size": len(batch)}})
            return 0
        self.stats.flushed += len(batch)
        self.stats.last_flush_at = utc_now(self.clock)
        return len(batch)

    async def _write(self, batch: list[Observation]) -> None:
        buckets: dict[tuple[str, str, str, datetime], _Bucket] = {}
        labels_of: dict[str, dict[str, Any]] = {}
        errors: dict[str, tuple[Observation, int]] = {}
        for item in batch:
            if item.kind == "error" and item.error is not None:
                key = fingerprint(
                    item.component,
                    str(item.error.get("category")),
                    str(item.error.get("type")),
                    str(item.error.get("message")),
                )
                first, count = errors.get(key, (item, 0))
                errors[key] = (item if item.at > first.at else first, count + 1)
                minute = item.at.replace(second=0, microsecond=0)
                counter = buckets.setdefault(
                    (item.component, "errors.recorded", "{}", minute), _Bucket("counter")
                )
                counter.values.append(1.0)
                labels_of["{}"] = {}
                continue
            minute = item.at.replace(second=0, microsecond=0)
            labels = dict(item.labels)
            lkey = labels_key(labels)
            labels_of[lkey] = labels
            bucket = buckets.setdefault((item.component, item.metric, lkey, minute), _Bucket(item.kind))
            bucket.values.append(item.value)
        async with self.database.unit_of_work() as uow:
            for (component, metric, lkey, minute), bucket in buckets.items():
                histogram = bucket.kind == "histogram"
                uow.session.add(
                    MetricSample(
                        sampled_at=minute,
                        component=component[:128],
                        metric=metric[:128],
                        labels=labels_of[lkey],
                        kind=bucket.kind,
                        count=len(bucket.values) if histogram else int(sum(bucket.values)),
                        sum=float(sum(bucket.values)),
                        max=max(bucket.values) if histogram else None,
                        p95=p95(bucket.values) if histogram else None,
                    )
                )
            for item, count in errors.values():
                assert item.error is not None
                await self.recorder.record(uow.session, item.component, item.error, item.at, count)

    async def rollup(self, now: datetime | None = None) -> int:
        """Roll complete hours (and days) since the last rollup; idempotent per bucket."""
        now = now or utc_now(self.clock)
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        written = 0
        async with self.database.unit_of_work() as uow:
            session = uow.session
            last = await session.scalar(select(func.max(Rollup.bucket)).where(Rollup.bucket_kind == "hour"))
            start = (last + HOUR) if last else await session.scalar(select(func.min(MetricSample.sampled_at)))
            if start is None:
                return 0
            start = max(start.replace(minute=0, second=0, microsecond=0), current_hour - 7 * DAY)
            rows = (
                (
                    await session.execute(
                        select(MetricSample).where(
                            MetricSample.sampled_at >= start, MetricSample.sampled_at < current_hour
                        )
                    )
                )
                .scalars()
                .all()
            )
            groups: dict[tuple[str, str, str, datetime], list[MetricSample]] = defaultdict(list)
            for row in rows:
                hour = row.sampled_at.replace(minute=0, second=0, microsecond=0)
                groups[(row.component, row.metric, labels_key(row.labels), hour)].append(row)
            for (component, metric, lkey, hour), samples in groups.items():
                written += await self._upsert(
                    session, component, metric, samples[0].labels, lkey, "hour", hour, samples
                )
            days = {
                hour.replace(hour=0)
                for (_, _, _, hour) in groups
                if hour.replace(hour=0) + DAY <= current_hour
            }
            for day in sorted(days):
                hourly = (
                    (
                        await session.execute(
                            select(Rollup).where(
                                Rollup.bucket_kind == "hour", Rollup.bucket >= day, Rollup.bucket < day + DAY
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                by_metric: dict[tuple[str, str, str], list[Rollup]] = defaultdict(list)
                for hour_row in hourly:
                    by_metric[(hour_row.component, hour_row.metric, hour_row.labels_key)].append(hour_row)
                for (component, metric, lkey), items in by_metric.items():
                    written += await self._upsert(
                        session, component, metric, items[0].labels, lkey, "day", day, items
                    )
        return written

    async def _upsert(
        self,
        session: Any,
        component: str,
        metric: str,
        labels: dict[str, Any],
        lkey: str,
        kind: str,
        bucket: datetime,
        items: Sequence[Any],
    ) -> int:
        maxima = [i.max for i in items if i.max is not None]
        p95s = [i.p95 for i in items if i.p95 is not None]
        values = {
            "component": component,
            "metric": metric,
            "labels": labels,
            "labels_key": lkey,
            "bucket_kind": kind,
            "bucket": bucket,
            "count": sum(i.count for i in items),
            "sum": float(sum(i.sum for i in items)),
            "p95": p95(p95s),
            "max": max(maxima) if maxima else None,
        }
        await session.execute(
            insert(Rollup).values(**values).on_conflict_do_update(constraint="uq_rollups_bucket", set_=values)
        )
        return 1
