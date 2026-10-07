"""Health API (T011, T014, T022): overview, detail sections, history."""

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.time import require_aware, utc_now
from portalab.modules.health.api.common import Module, tier_of
from portalab.modules.health.permissions import SERVICES_READ

router = APIRouter(prefix="/api/v1", tags=["health"])
MAX_RANGE = timedelta(days=93)


@router.get("/services/health")
async def overview(_: Annotated[Principal, require(SERVICES_READ)], module: Module) -> dict[str, Any]:
    states = {view.service_id: view for view in await module.reader.all()}
    items = []
    for info in await module.state.services():
        view = states.get(info.id)
        items.append(
            {
                "id": info.id,
                "name": info.name,
                "connector": info.connector,
                "state": view.state if view else "unknown",
                "since": view.since.isoformat() if view else None,
                "availability": view.availability if view else None,
                "link": info.link,  # 027: where members open it (public address), when there is one
                "as_of": view.as_of.isoformat() if view else utc_now(module.state.clock).isoformat(),
            }
        )
    return {"items": items}


async def _known(module: Any, service_id: str) -> None:
    if await module.state.service_info(service_id) is None and await module.reader.get(service_id) is None:
        raise NotFound("No such service.", code="service.not_found")


@router.get("/services/{service_id}/health")
async def detail(
    principal: Annotated[Principal, require(SERVICES_READ)], service_id: str, request: Request, module: Module
) -> dict[str, Any]:
    await _known(module, service_id)
    return await module.detail.detail(service_id, await tier_of(request, principal))


@router.get("/services/{service_id}/health/history")
async def history(
    principal: Annotated[Principal, require(SERVICES_READ)],
    service_id: str,
    request: Request,
    module: Module,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
) -> dict[str, Any]:
    await _known(module, service_id)
    now = utc_now(module.state.clock)
    try:
        upper = require_aware(end) if end else now
        lower = require_aware(start) if start else upper - timedelta(days=1)
    except ValueError as exc:
        raise ValidationFailed("Instants must carry a time zone offset.") from exc
    if lower >= upper or upper - lower > MAX_RANGE:
        raise ValidationFailed("The range must be positive and at most 93 days.", code="health.invalid_range")
    tier = await tier_of(request, principal)
    result = await module.history.history(
        service_id, lower, upper, with_metrics=tier.infrastructure or tier.manage
    )
    if tier.infrastructure or tier.manage:
        result["errors"] = await module.history.recent_errors(service_id)
    return result
