"""Probe scheduling (T009): a periodic ``health.probe_sweep`` keeps sample partitions ahead, reconciles
maintenance windows, enqueues one ``health.probe_service`` job per probed service (dedup per service and
probe slot) and re-derives services that have no probe (they turn Unknown once stale)."""

from datetime import timedelta
from typing import Any

from portalab.capabilities.health import HEALTH_PROBE
from portalab.core.jobs.periodic import register_periodic, slot_of
from portalab.core.jobs.queue import HEALTH_QUEUE, enqueue
from portalab.core.jobs.registry import JobRegistry
from portalab.core.partitions import ensure_month_partitions
from portalab.core.time import utc_now
from portalab.modules.health.maintenance.service import MaintenanceService
from portalab.modules.health.observability import log
from portalab.modules.health.probes.runner import ProbeRunner

OWNER = "module:health"
PROBE_JOB = "health.probe_service"
SWEEP_JOB = "health.probe_sweep"


class ProbeScheduler:
    def __init__(self, runner: ProbeRunner, maintenance: MaintenanceService) -> None:
        self.runner = runner
        self.state = runner.state
        self.maintenance = maintenance

    async def ensure_partitions(self) -> None:
        now = utc_now(self.state.clock)
        async with self.state.database.unit_of_work() as uow:
            for table in ("health_samples", "infra_samples"):
                try:
                    async with uow.session.begin_nested():
                        await ensure_month_partitions(uow.session, "health", table, now)
                except Exception:
                    log.warning("partition upkeep failed", extra={"fields": {"table": table}})

    async def sweep(self) -> int:
        await self.ensure_partitions()
        await self.maintenance.reconcile()
        now = utc_now(self.state.clock)
        interval = timedelta(seconds=max(self.state.config.probe_interval_seconds, 10))
        slot = slot_of(now, interval).strftime("%Y%m%dT%H%M%S")
        probed = {reg.instance_ref for reg in self.state.capabilities.system_providers(HEALTH_PROBE)}
        async with self.state.database.unit_of_work() as uow:
            for service_id in sorted(probed):
                await enqueue(
                    uow.session,
                    kind=PROBE_JOB,
                    queue=HEALTH_QUEUE,  # 027: probes never wait behind syncs or bulk work
                    payload={"service_id": service_id},
                    dedup_key=f"{PROBE_JOB}:{service_id}:{slot}",
                    max_attempts=1,
                    clock=self.state.clock,
                )
        for info in await self.state.services():
            if info.id not in probed:
                await self.state.evaluate(info.id)
        return len(probed)

    async def handle(self, payload: dict[str, Any]) -> None:
        await self.runner.probe(str(payload["service_id"]))

    def register(self, jobs: JobRegistry) -> Any:
        jobs.register(
            PROBE_JOB,
            self.handle,
            idempotency="a duplicate probe adds one more sample; state derivation is idempotent",
            timeout_seconds=120,
            owner=OWNER,
        )
        return register_periodic(
            jobs,
            self.state.database,
            SWEEP_JOB,
            timedelta(seconds=max(self.state.config.probe_interval_seconds, 10)),
            self.sweep,
            owner=OWNER,
            clock=self.state.clock,
            queue=HEALTH_QUEUE,
        )
