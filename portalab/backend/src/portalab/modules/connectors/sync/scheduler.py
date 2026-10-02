"""Sync scheduling (T023): a periodic ``connectors.sync_due`` sweep enqueues one ``connectors.sync_service``
job per due service, deduplicated per ``(service, window)``; manual syncs and resyncs use the same job kind
with a per-request key. The handler is idempotent: the runner holds a per-service advisory lock and sinks
upsert by ``(source_system, external_id)``."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.authz_port import Principal
from portalab.core.ids import new_id
from portalab.core.jobs.periodic import register_periodic, slot_of
from portalab.core.jobs.queue import EnqueueResult, enqueue
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import utc_now
from portalab.modules.connectors.models import Service, SyncState
from portalab.modules.connectors.sync.runner import SyncRunner

OWNER = "module:connectors"
SYNC_KIND = "connectors.sync_service"
DUE_KIND = "connectors.sync_due"
SWEEP_EVERY = timedelta(minutes=1)


class SyncScheduler:
    def __init__(self, runner: SyncRunner) -> None:
        self.runner = runner
        self.manager = runner.manager

    async def enqueue(
        self,
        session: AsyncSession,
        service_id: UUID,
        *,
        kind: str,
        requested_by: UUID | None = None,
        allow_large_deletion: bool = False,
        dedup_key: str | None = None,
    ) -> EnqueueResult:
        payload: dict[str, Any] = {"service_id": str(service_id), "kind": kind}
        if requested_by is not None:
            payload["requested_by"] = str(requested_by)
        if allow_large_deletion:
            payload["allow_large_deletion"] = True
        return await enqueue(
            session,
            kind=SYNC_KIND,
            payload=payload,
            dedup_key=dedup_key or f"connectors.sync:{service_id}:{kind}:{new_id()}",
            max_attempts=1,
            clock=self.manager.clock,
        )

    async def enqueue_due(self) -> int:
        now = utc_now(self.manager.clock)
        default = self.manager.config.default_sync_interval_seconds
        queued = 0
        async with self.manager.database.unit_of_work() as uow:
            rows = (
                await uow.session.execute(
                    select(Service.id, Service.sync_interval_seconds)
                    .join(SyncState, SyncState.service_id == Service.id)
                    .where(
                        Service.state.in_(("enabled", "error", "unavailable")),
                        SyncState.status != "running",
                        or_(SyncState.next_run_at.is_(None), SyncState.next_run_at <= now),
                    )
                )
            ).all()
            for service_id, interval in rows:
                window = slot_of(now, timedelta(seconds=max(interval or default, 60)))
                result = await self.enqueue(
                    uow.session,
                    service_id,
                    kind="scheduled",
                    dedup_key=f"connectors.sync:{service_id}:scheduled:{window.strftime('%Y%m%dT%H%M%S')}",
                )
                queued += int(result.created)
        return queued

    async def handle(self, payload: dict[str, Any]) -> None:
        requested_by = payload.get("requested_by")
        actor = Principal(user_id=UUID(requested_by)) if requested_by else None
        kind = payload.get("kind", "scheduled")
        await self.runner.run(
            UUID(payload["service_id"]),
            kind=kind,
            actor=actor,
            allow_large_deletion=bool(payload.get("allow_large_deletion", False)),
        )

    def register(self, jobs: JobRegistry) -> Any:
        jobs.register(
            SYNC_KIND,
            self.handle,
            idempotency="per-service advisory lock; sinks upsert by (source_system, external_id)",
            timeout_seconds=3600,
            owner=OWNER,
        )
        return register_periodic(
            jobs,
            self.manager.database,
            DUE_KIND,
            SWEEP_EVERY,
            self.enqueue_due,
            owner=OWNER,
            clock=self.manager.clock,
        )
