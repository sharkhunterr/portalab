"""Probe runner (T009; R2, FR-005..009): one probe of one service through its ``service.health_probe``
provider (failure-isolated by 005), recorded as a sample — failures also update the actionable
``recent_errors`` list — then the service state is re-derived. A probe that times out or crashes is a
failed sample; a service without a probe provider just gets re-derived (it becomes Unknown when stale)."""

import asyncio
import time
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.health import HEALTH_PROBE, ProbeResult
from portalab.capabilities.results import Available, CapabilityResult
from portalab.core.logging import redact_text
from portalab.core.time import utc_now
from portalab.modules.health.models import HealthSample, RecentError
from portalab.modules.health.observability import metric_part, metrics
from portalab.modules.health.state.service import StateService


class ProbeRunner:
    def __init__(self, state: StateService) -> None:
        self.state = state

    def provider(self, service_id: str) -> Any:
        for registration in self.state.capabilities.system_providers(HEALTH_PROBE):
            if registration.instance_ref == service_id:
                return registration.provider
        return None

    async def probe(self, service_id: str) -> bool | None:
        """Probe once; ``True``/``False`` for the sample written, ``None`` when there is no probe."""
        provider = self.provider(service_id)
        if provider is None:
            await self.state.evaluate(service_id)
            return None
        started = time.monotonic()
        try:
            result: CapabilityResult[ProbeResult] = await asyncio.wait_for(
                provider.probe(), timeout=self.state.config.probe_interval_seconds
            )
        except Exception:
            result = None  # type: ignore[assignment]
        elapsed_ms = (time.monotonic() - started) * 1000
        checked_at = utc_now(self.state.clock)
        if isinstance(result, Available) and isinstance(result.value, ProbeResult):
            probe: ProbeResult = result.value
            ok = probe.reachable and probe.error_code is None
            latency = probe.latency_ms if probe.latency_ms is not None else elapsed_ms
            code = probe.error_code or (None if ok else "unreachable")
            if ok and probe.warning:
                code = probe.warning  # answers, but warns: degraded, not an outage
            message = probe.detail or ("The service did not answer." if not ok else "")
        else:
            state = getattr(result, "state", "unavailable")
            ok, latency, code = False, None, state
            message = {
                "timeout": "The service did not answer in time.",
                "authentication_failed": "The service rejected the configured credentials.",
                "invalid_response": "The service answered with an unexpected response.",
            }.get(state, "The service cannot be reached.")
        message = redact_text(message)[:500]
        async with self.state.database.unit_of_work() as uow:
            uow.session.add(
                HealthSample(
                    service_id=service_id,
                    checked_at=checked_at,
                    ok=ok,
                    latency_ms=latency,
                    error_code=code,
                    detail={"message": message} if message else None,
                )
            )
            if code:
                await uow.session.execute(
                    insert(RecentError)
                    .values(
                        service_id=service_id,
                        occurred_at=checked_at,
                        code=code,
                        message=message,
                        count=1,
                        last_seen_at=checked_at,
                    )
                    .on_conflict_do_update(
                        constraint="uq_recent_errors_code",
                        set_={"count": RecentError.count + 1, "last_seen_at": checked_at, "message": message},
                    )
                )
        metrics.increment(f"health.probes.{'ok' if ok else 'failed'}")
        if latency is not None:
            metrics.gauge(f"health.probe_latency_ms.{metric_part(service_id)}", latency)
        await self.state.evaluate(service_id)
        return ok
