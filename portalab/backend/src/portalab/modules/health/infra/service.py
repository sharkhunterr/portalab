"""Infrastructure metrics (T019; R5, FR-013..015): fetched through the service's ``infrastructure.metrics``
provider, stored as short-retention samples, and returned **per metric** — a metric the host does not
report is ``not_available`` with a reason, never zero; a partial provider still shows the others."""

from typing import Any

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
