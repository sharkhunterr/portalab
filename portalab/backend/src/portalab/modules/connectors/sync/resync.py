"""Resynchronization (T030; FR-022..024, US7).

``partial``: re-reads the source from scratch (cursor reset) and upserts; nothing is deactivated except
explicit removals. ``full``: additionally deactivates this service's records the source no longer lists —
only records with **this service's provenance**, never native portal data or other services' rows. A full
resync is sensitive (confirmation + audit); one that would deactivate more than the configured ratio is
held back (``deletion_confirmation_required``) until it is re-requested with ``allow_large_deletion``.
"""

from typing import Literal
from uuid import UUID

from portalab.core.authz_port import Principal
from portalab.core.jobs.queue import EnqueueResult
from portalab.core.time import utc_now
from portalab.modules.connectors.services.common import ServiceDisabled, audit, publish, service_ref
from portalab.modules.connectors.sync.scheduler import SyncScheduler

Mode = Literal["partial", "full"]


class ResyncService:
    def __init__(self, scheduler: SyncScheduler) -> None:
        self.scheduler = scheduler
        self.manager = scheduler.manager

    async def request(
        self, actor: Principal, service_id: UUID, mode: Mode, *, allow_large_deletion: bool = False
    ) -> EnqueueResult:
        now = utc_now(self.manager.clock)
        async with self.manager.database.unit_of_work() as uow:
            row = await self.manager._row(uow.session, service_id)
            if row.state not in ("enabled", "error", "unavailable"):
                raise ServiceDisabled("This service is not enabled; it cannot be resynchronized.")
            result = await publish(
                self.manager.events,
                uow.session,
                "connector.resync_requested",
                {"connector": row.connector_key, "service_id": str(service_id), "mode": mode},
                service_id=service_id,
                actor=actor,
                occurred_at=now,
            )
            await audit(
                self.manager.audit,
                uow.session,
                "connector.resync_requested",
                actor,
                resource=service_ref(service_id),
                context={"mode": mode, "allow_large_deletion": allow_large_deletion},
                sensitive=mode == "full",
                event_id=result.event_id,
            )
            return await self.scheduler.enqueue(
                uow.session,
                service_id,
                kind=f"resync_{mode}",
                requested_by=actor.user_id,
                allow_large_deletion=allow_large_deletion and mode == "full",
            )
