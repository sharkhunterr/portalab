"""Observability API (T010, T013, T021, T024, T028, T031): admin-only by default (``observability.read``;
Support sees redacted context, holders of ``observability.manage`` the full context); decisions on errors
and anomalies are audited."""

from datetime import timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.errors import NotFound, Unavailable
from portalab.core.time import utc_now
from portalab.modules.observability.components.evaluator import health_out
from portalab.modules.observability.components.performance import performance, window
from portalab.modules.observability.module import ObservabilityModule
from portalab.modules.observability.permissions import OBSERVABILITY_MANAGE, OBSERVABILITY_READ
from portalab.modules.observability.trends import trends

router = APIRouter(prefix="/api/v1/admin/observability", tags=["observability"])


def observability_module(request: Request) -> ObservabilityModule:
    module = getattr(request.app.state, "observability_module", None)
    if not isinstance(module, ObservabilityModule):
        raise Unavailable("Observability is not available.", code="observability.unavailable")
    return module


Module = Annotated[ObservabilityModule, Depends(observability_module)]
Reader = Annotated[Principal, require(OBSERVABILITY_READ)]
Manager = Annotated[Principal, require(OBSERVABILITY_MANAGE)]


async def full_context(request: Request, principal: Principal) -> bool:
    authorizer: Authorizer = request.app.state.authorizer
    return await authorizer.is_allowed(principal, OBSERVABILITY_MANAGE, None)


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: str = Field(min_length=1, max_length=2000)


@router.get("/overview")
async def overview(principal: Reader, request: Request, module: Module) -> dict[str, Any]:
    full = await full_context(request, principal)
    return {
        "portal": await module.overview.portal_status(),
        "problems": await module.overview.problems(full_context=full),
        "components": [
            health_out(row) if full else {**health_out(row), "reason": {}}
            for row in await module.evaluator.all()
        ],
    }


@router.get("/components/{component}")
async def component(principal: Reader, component: str, request: Request, module: Module) -> dict[str, Any]:
    row = await module.evaluator.current(component)
    if row is None:
        raise NotFound("No such component.", code="observability.component_not_found")
    declared = {c.name: c for c in await module.registry.components()}.get(component)
    out = health_out(row)
    if not await full_context(request, principal):
        out["reason"] = {"unobserved": row.reason.get("unobserved", [])}
    out["diagnostics"] = [
        {"key": a.key, "label": a.label, "method": a.method, "path": a.path, "permission": a.permission}
        for a in (declared.diagnostics if declared else ())
    ]
    return out


@router.get("/errors")
async def errors(
    principal: Reader,
    request: Request,
    module: Module,
    state: Literal["open", "acknowledged", "resolved"] | None = None,
    component: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    full = await full_context(request, principal)
    return {
        "items": await module.errors.errors(state=state, component=component, full_context=full, limit=limit)
    }


@router.post("/errors/{error_id}/ack")
async def acknowledge(principal: Manager, error_id: UUID, module: Module) -> dict[str, Any]:
    return await module.errors.transition(principal, error_id, "acknowledged")


@router.post("/errors/{error_id}/resolve")
async def resolve(principal: Manager, error_id: UUID, body: ResolveIn, module: Module) -> dict[str, Any]:
    return await module.errors.transition(principal, error_id, "resolved", body.resolution)


@router.get("/anomalies")
async def anomalies(
    _: Reader,
    module: Module,
    status: Literal["candidate", "pending_validation", "escalated", "dismissed", "resolved"] | None = None,
) -> dict[str, Any]:
    return {"items": await module.escalation.anomalies(status=status)}


@router.post("/anomalies/{anomaly_id}/{decision}")
async def decide(
    principal: Manager, anomaly_id: UUID, decision: Literal["validate", "dismiss"], module: Module
) -> dict[str, Any]:
    from portalab.modules.observability.escalation.service import anomaly_out

    return anomaly_out(await module.escalation.decide(principal, anomaly_id, decision))


@router.get("/performance")
async def performance_view(
    _: Reader, module: Module, hours: Annotated[int, Query(ge=1, le=744)] = 24
) -> dict[str, Any]:
    since = window(hours, utc_now(module.clock))
    return {"items": await performance(module.database, since, slow_ms=module.config.slow_request_ms)}


@router.get("/trends")
async def trends_view(
    _: Reader,
    module: Module,
    metric: str = Query(default="http.request", max_length=128),
    component: str | None = Query(default=None, max_length=128),
    days: Annotated[int, Query(ge=1, le=400)] = 30,
    bucket: Literal["hour", "day"] = "day",
) -> dict[str, Any]:
    since = utc_now(module.clock) - timedelta(days=days)
    return await trends(module.database, metric=metric, component=component, since=since, bucket=bucket)
