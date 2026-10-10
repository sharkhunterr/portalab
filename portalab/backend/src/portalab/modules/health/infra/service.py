"""Infrastructure metrics (T019; R5, FR-013..015): fetched through the service's ``infrastructure.metrics``
provider, stored as short-retention samples, and returned **per metric** — a metric the host does not
report is ``not_available`` with a reason, never zero; a partial provider still shows the others."""

import time
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select

from portalab.capabilities.health import INFRA_METRICS, METRICS, MetricValue, NotAvailable
from portalab.capabilities.results import Available
from portalab.core.time import utc_now
from portalab.modules.health.models import InfraSample
from portalab.modules.health.state.service import StateService


class InfraMetricsService:
    def __init__(self, state: StateService) -> None:
        self.state = state

    def provider(self, service_id: str) -> Any:
        for registration in self.state.capabilities.system_providers(INFRA_METRICS):
            if registration.instance_ref == service_id:
                return registration.provider
        return None

    async def fetch(self, service_id: str, metrics: list[str] | None = None) -> dict[str, Any]:
        wanted = [m for m in (metrics or list(METRICS)) if m in METRICS]
        provider = self.provider(service_id)
        if provider is None:
            return {"state": "unavailable", "detail": "No metrics provider for this service.", "metrics": {}}
        result = await provider.fetch(wanted)
        if not isinstance(result, Available):
            return {
                "state": "unavailable",
                "detail": "The metrics provider did not answer.",
                "metrics": {m: {"available": False, "reason": "provider unavailable"} for m in wanted},
            }
        now = utc_now(self.state.clock)
        values: dict[str, Any] = {}
        async with self.state.database.unit_of_work() as uow:
            for metric in wanted:
                item = result.value.get(metric, NotAvailable("not reported"))
                if isinstance(item, MetricValue):
                    values[metric] = {"available": True, "value": item.value, "unit": item.unit}
                    uow.session.add(
                        InfraSample(
                            service_id=service_id,
                            sampled_at=now,
                            metric=metric,
                            value=item.value,
                            unit=item.unit,
                            available=True,
                        )
                    )
                else:
                    reason = item.reason if isinstance(item, NotAvailable) else "not reported"
                    values[metric] = {"available": False, "reason": reason}
                    uow.session.add(
                        InfraSample(service_id=service_id, sampled_at=now, metric=metric, available=False)
                    )
        partial = any(not v["available"] for v in values.values())
        return {"state": "partial" if partial else "available", "as_of": now.isoformat(), "metrics": values}


class InfraHistoryService:
    """#52: the metrics over time, for charts — the stored samples averaged into buckets, and the values
    right now (asked to the service, kept two seconds, never stored: a live chart may ask every second)."""

    def __init__(self, infra: InfraMetricsService) -> None:
        self.infra = infra
        self._now: dict[str, tuple[float, Mapping[str, Any]]] = {}

    def services(self) -> list[str]:
        return [
            str(r.instance_ref)
            for r in self.infra.state.capabilities.system_providers(INFRA_METRICS)
            if r.instance_ref is not None
        ]

    async def series(
        self, service_id: str, metrics: Sequence[str], since: datetime, *, points: int = 240
    ) -> dict[str, list[tuple[datetime, float]]]:
        now = utc_now(self.infra.state.clock)
        width = max(1.0, (now - since).total_seconds() / max(points, 1))
        async with self.infra.state.database.session() as session:
            rows = await session.execute(
                select(InfraSample.metric, InfraSample.sampled_at, InfraSample.value)
                .where(
                    InfraSample.service_id == service_id,
                    InfraSample.metric.in_(list(metrics)),
                    InfraSample.sampled_at >= since,
                    InfraSample.available.is_(True),
                )
                .order_by(InfraSample.sampled_at)
            )
            buckets: dict[str, dict[int, list[float]]] = {m: {} for m in metrics}
            for metric, at, value in rows:
                if value is None:
                    continue
                slot = int((at - since).total_seconds() // width)
                buckets[metric].setdefault(slot, []).append(float(value))
        out: dict[str, list[tuple[datetime, float]]] = {}
        for metric, slots in buckets.items():
            out[metric] = [
                (
                    datetime.fromtimestamp(since.timestamp() + (slot + 0.5) * width, tz=since.tzinfo),
                    sum(v) / len(v),
                )
                for slot, v in sorted(slots.items())
            ]
        return out

    async def current(self, service_id: str, metrics: Sequence[str]) -> dict[str, MetricValue | None]:
        cached = self._now.get(service_id)
        if cached is None or time.monotonic() - cached[0] > 2.0:
            provider = self.infra.provider(service_id)
            values: Mapping[str, Any] = {}
            if provider is not None:
                result = await provider.fetch(list(METRICS))
                if isinstance(result, Available):
                    values = result.value
            cached = (time.monotonic(), values)
            self._now[service_id] = cached
        return {m: (cached[1].get(m) if isinstance(cached[1].get(m), MetricValue) else None) for m in metrics}
