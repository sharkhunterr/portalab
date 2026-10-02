"""``health.service_state`` capability (T010): the derived state of a service with its freshness
(``as_of``) and 24 h availability — the read model for Dashboard, Media, Statistics and Observability."""

from datetime import timedelta

from sqlalchemy import select

from portalab.capabilities.health import ServiceStateView
from portalab.core.time import utc_now
from portalab.modules.health.models import ServiceState
from portalab.modules.health.rollups.availability import availability
from portalab.modules.health.state.service import StateService

DAY = timedelta(hours=24)


class ServiceStateReaderImpl:
    def __init__(self, state: StateService) -> None:
        self.state = state

    async def _view(self, row: ServiceState) -> ServiceStateView:
        now = utc_now(self.state.clock)
        async with self.state.database.session() as session:
            ratio = (await availability(session, row.service_id, now - DAY, now)).ratio
        return ServiceStateView(
            service_id=row.service_id,
            state=row.state,  # type: ignore[arg-type]
            since=row.state_since,
            last_check_at=row.last_check_at,
            availability=ratio,
            as_of=now,
        )

    async def get(self, service_id: str) -> ServiceStateView | None:
        async with self.state.database.session() as session:
            row = await session.get(ServiceState, service_id)
        return await self._view(row) if row else None

    async def all(self) -> list[ServiceStateView]:
        async with self.state.database.session() as session:
            rows = (
                (await session.execute(select(ServiceState).order_by(ServiceState.service_id)))
                .scalars()
                .all()
            )
        return [await self._view(row) for row in rows]
