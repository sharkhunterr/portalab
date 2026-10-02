"""Service detail assembler (T022; R7, FR-010/026..031).

The detail page is a set of **independent sections**, each resolved with its own timeout and reported as
``{"state": available|no-data|unavailable, "as_of", "data"}``: a slow or failing section never fails the
response. Service State, Maintenance, Incidents, Tickets and Sync State stay distinct sections. The shape
depends on the caller's permissions, enforced here (server side): ``services.read`` gets state,
availability, maintenance, incidents, sync and history; ``infrastructure.read`` adds availability details,
recent errors, tickets and infrastructure; ``services.manage`` adds operations.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from portalab.core.time import utc_now
from portalab.modules.health.detail.history import HistoryQuery
from portalab.modules.health.detail.incidents import IncidentLinkService
from portalab.modules.health.infra.service import InfraMetricsService
from portalab.modules.health.maintenance.service import MaintenanceService
from portalab.modules.health.models import ServiceState
from portalab.modules.health.observability import metric_part, metrics
from portalab.modules.health.operations.service import OperationsService
from portalab.modules.health.rollups.availability import availability
from portalab.modules.health.state.service import StateService

DAY = timedelta(hours=24)
SECTIONS_STANDARD = ("state", "availability", "maintenance", "incidents", "sync", "history")
SECTIONS_INFRA = ("errors", "tickets", "infrastructure")
SECTIONS_MANAGE = ("operations",)


@dataclass(frozen=True, slots=True)
class Tier:
    infrastructure: bool = False
    manage: bool = False

    def sections(self) -> tuple[str, ...]:
        return (
            SECTIONS_STANDARD
            + (SECTIONS_INFRA if self.infrastructure or self.manage else ())
            + (SECTIONS_MANAGE if self.manage else ())
        )


class DetailAssembler:
    def __init__(
        self,
        state: StateService,
        maintenance: MaintenanceService,
        history: HistoryQuery,
        incidents: IncidentLinkService,
        infra: InfraMetricsService,
        operations: OperationsService,
    ) -> None:
        self.state = state
        self.maintenance = maintenance
        self.history = history
        self.incidents = incidents
        self.infra = infra
        self.operations = operations
        self.overrides: dict[str, Callable[[str, Tier], Awaitable[Any]]] = {}  # test seam

    async def _state(self, service_id: str, tier: Tier) -> Any:
        async with self.state.database.session() as session:
            row = await session.get(ServiceState, service_id)
        if row is None:
            return None
        data: dict[str, Any] = {"state": row.state, "since": row.state_since.isoformat()}
        if tier.infrastructure or tier.manage:
            data |= {
                "reason": row.reason,
                "last_check_at": row.last_check_at.isoformat() if row.last_check_at else None,
                "last_ok_at": row.last_ok_at.isoformat() if row.last_ok_at else None,
            }
        return data

    async def _availability(self, service_id: str, tier: Tier) -> Any:
        now = utc_now(self.state.clock)
        async with self.state.database.session() as session:
            result = await availability(session, service_id, now - DAY, now)
        if result.samples == 0:
            return None
        if tier.infrastructure or tier.manage:
            return result.as_dict() | {"window_hours": 24}
        return {"availability": result.ratio, "window_hours": 24}

    async def _sync(self, service_id: str, tier: Tier) -> Any:
        info = await self.state.service_info(service_id)
        if info is None:
            return None
        data: dict[str, Any] = {
            "status": info.sync_status,
            "last_success_at": info.last_sync_success_at.isoformat() if info.last_sync_success_at else None,
        }
        if tier.infrastructure or tier.manage:
            data["last_error"] = info.last_sync_error
        return data

    async def _history(self, service_id: str, tier: Tier) -> Any:
        now = utc_now(self.state.clock)
        result = await self.history.history(service_id, now - DAY, now)
        return {"transitions": result["transitions"]} if result["transitions"] else None

    async def _maintenance(self, service_id: str, tier: Tier) -> Any:
        return await self.maintenance.windows(service_id=service_id) or None

    async def _incidents(self, service_id: str, tier: Tier) -> Any:
        if not self.incidents.available:
            return None
        return await self.incidents.open_for_service(service_id) or None

    async def _tickets(self, service_id: str, tier: Tier) -> Any:
        return await self.incidents.tickets_for_service(service_id) or None

    async def _errors(self, service_id: str, tier: Tier) -> Any:
        return await self.history.recent_errors(service_id) or None

    async def _infrastructure(self, service_id: str, tier: Tier) -> Any:
        result = await self.infra.fetch(service_id)
        if result["state"] == "unavailable" and not result["metrics"]:
            raise LookupError(result.get("detail", "no metrics"))
        return result

    async def _operations(self, service_id: str, tier: Tier) -> Any:
        return await self.operations.list(service_id) or None

    async def _section(self, name: str, service_id: str, tier: Tier) -> dict[str, Any]:
        resolver = self.overrides.get(name) or getattr(self, f"_{name}")
        as_of = utc_now(self.state.clock).isoformat()
        try:
            data = await asyncio.wait_for(
                resolver(service_id, tier), timeout=self.state.config.section_timeout_seconds
            )
        except TimeoutError:
            metrics.increment(f"health.section_failures.{metric_part(name)}")
            return {"state": "unavailable", "as_of": as_of, "detail": "This section did not load in time."}
        except Exception:
            metrics.increment(f"health.section_failures.{metric_part(name)}")
            return {
                "state": "unavailable",
                "as_of": as_of,
                "detail": "This section is unavailable right now.",
            }
        if data is None:
            return {"state": "no-data", "as_of": as_of, "data": None}
        return {"state": "available", "as_of": as_of, "data": data}

    async def detail(self, service_id: str, tier: Tier) -> dict[str, Any]:
        info = await self.state.service_info(service_id)
        names = tier.sections()
        sections = await asyncio.gather(*(self._section(name, service_id, tier) for name in names))
        return {
            "service": {
                "id": service_id,
                "name": info.name if info else None,
                "connector": info.connector if info else None,
            },
            "sections": dict(zip(names, sections, strict=True)),
        }
