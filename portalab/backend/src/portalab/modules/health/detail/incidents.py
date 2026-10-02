"""Incident links (T023; R8): incidents live in Support (016) behind the ``support.incidents`` port; 006
only records ``service_incident_links`` and displays open incidents. Without a provider the section is
simply empty — there is no local incident model."""

from typing import Any

from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.health import INCIDENTS, SERVICE_TICKETS
from portalab.core.time import utc_now
from portalab.modules.health.models import ServiceIncidentLink
from portalab.modules.health.state.service import StateService


class IncidentLinkService:
    def __init__(self, state: StateService) -> None:
        self.state = state

    def _port(self, name: str) -> Any:
        providers = self.state.capabilities.system_providers(name)
        return providers[0].provider if providers else None

    @property
    def available(self) -> bool:
        return self._port(INCIDENTS) is not None

    async def open_for_service(self, service_id: str) -> list[dict[str, Any]]:
        port = self._port(INCIDENTS)
        if port is None:
            return []
        return [
            {"id": i.id, "title": i.title, "status": i.status, "opened_at": i.opened_at.isoformat()}
            for i in await port.open_for_service(service_id)
        ]

    async def tickets_for_service(self, service_id: str) -> list[dict[str, Any]] | None:
        port = self._port(SERVICE_TICKETS)
        if port is None:
            return None
        return [
            {"id": t.id, "title": t.title, "status": t.status}
            for t in await port.open_for_service(service_id)
        ]

    async def link(self, service_id: str, incident_id: str) -> None:
        async with self.state.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(ServiceIncidentLink)
                .values(service_id=service_id, incident_id=incident_id, linked_at=utc_now(self.state.clock))
                .on_conflict_do_nothing(constraint="uq_service_incident_links")
            )
        port = self._port(INCIDENTS)
        if port is not None:
            await port.link(service_id, incident_id)
