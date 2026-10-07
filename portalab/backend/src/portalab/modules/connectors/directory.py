"""``connectors.directory`` provider (spec 006 input): configured services with their connection and
sync state, so Health can list and describe services without importing this module."""

from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.health import INCIDENT_AFTER, ServiceInfo
from portalab.modules.connectors.models import Service, SyncRun, SyncState
from portalab.modules.connectors.services.manager import ServiceManager


def _link(row: Service) -> str | None:
    """027: the public address set by an administrator, else the connection address when it is https
    (a plain-http or internal address is not offered to members)."""
    if row.public_url:
        return row.public_url
    base = str((row.config or {}).get("base_url") or "")
    return base if base.startswith("https://") else None


def _incident_after(row: Service) -> int | None:
    """027: minutes of outage before an incident — the service's own setting, else its importance's."""
    if row.incident_after_minutes is not None:
        return row.incident_after_minutes or None  # 0: never
    return INCIDENT_AFTER.get(row.importance, 10)


class ConnectorServiceDirectory:
    def __init__(self, manager: ServiceManager) -> None:
        self.manager = manager

    async def _info(self, row: Service, state: SyncState | None, last_error: str | None) -> ServiceInfo:
        return ServiceInfo(
            id=str(row.id),
            name=row.name,
            connector=row.connector_key,
            state=row.state,
            sync_status=state.status if state else "idle",
            last_sync_success_at=state.last_success_at if state else None,
            last_sync_attempt_at=state.last_attempt_at if state else None,
            last_sync_error=last_error,
            link=_link(row),
            importance=row.importance,
            incident_after_minutes=_incident_after(row),
            incident_auto_resolve=row.incident_auto_resolve,
        )

    async def services(self) -> list[ServiceInfo]:
        async with self.manager.database.session() as session:
            rows = (await session.execute(select(Service).order_by(Service.name, Service.id))).scalars().all()
            states = {s.service_id: s for s in (await session.execute(select(SyncState))).scalars()}
            return [await self._info(row, states.get(row.id), None) for row in rows]

    async def service(self, service_id: str) -> ServiceInfo | None:
        try:
            parsed = UUID(service_id)
        except ValueError:
            return None
        async with self.manager.database.session() as session:
            row = await session.get(Service, parsed)
            if row is None:
                return None
            state = await session.get(SyncState, parsed)
            last_error = await session.scalar(
                select(SyncRun.last_error)
                .where(SyncRun.service_id == parsed, SyncRun.status != "succeeded")
                .order_by(SyncRun.finished_at.desc())
                .limit(1)
            )
            return await self._info(row, state, last_error)
