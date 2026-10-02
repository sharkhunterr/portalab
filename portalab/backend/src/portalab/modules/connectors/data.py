"""``connectors.service_data`` provider (T031; spec 021 FR-020..022, CD-014).

Disconnecting keeps everything; an explicit, separately authorized purge (021, ``services.purge``) asks
every registered ``RecordSink`` to erase the rows imported from one service and resets its sync cursor.
The technical sync history stays until its retention window (021 engine) removes it.
"""

from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.record_sink import SinkRegistry, default_sinks
from portalab.core.time import utc_now
from portalab.modules.connectors.models import Service, SyncState
from portalab.modules.connectors.services.common import publish
from portalab.modules.connectors.services.manager import SYSTEM, ServiceManager
from portalab.modules.connectors.sync.runner import source_ref


class ServiceDataOwner:
    def __init__(self, manager: ServiceManager, sinks: SinkRegistry = default_sinks) -> None:
        self.manager = manager
        self.sinks = sinks

    async def _service(self, service_id: str) -> Service | None:
        try:
            parsed = UUID(service_id)
        except ValueError:
            return None
        async with self.manager.database.session() as session:
            return (await session.execute(select(Service).where(Service.id == parsed))).scalar_one_or_none()

    async def has_service(self, service_id: str) -> bool:
        return await self._service(service_id) is not None

    async def purge_service_data(self, service_id: str) -> int:
        row = await self._service(service_id)
        if row is None:
            return 0
        ref = source_ref(row)
        purged = 0
        for _, sink in self.sinks.all():
            purged += await sink.purge(ref)
        async with self.manager.database.unit_of_work() as uow:
            state = await uow.session.get(SyncState, row.id, with_for_update=True)
            if state is not None:
                state.cursor = None
            await publish(
                self.manager.events,
                uow.session,
                "connector.data_purged",
                {"connector": row.connector_key, "service_id": str(row.id), "purged": purged},
                service_id=row.id,
                actor=SYSTEM,
                occurred_at=utc_now(self.manager.clock),
            )
        return purged
