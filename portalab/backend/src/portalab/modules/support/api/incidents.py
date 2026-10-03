"""Incidents API (T011): public read (``incidents.read``; affected services named only to holders of
``services.read``; evidence and authors only for ``incidents.manage``) and the staff console
(``incidents.manage``, audited, ``If-Match: <version>``)."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable, ValidationFailed
from portalab.modules.support.incidents.service import IncidentView
from portalab.modules.support.module import SupportModule
from portalab.modules.support.permissions import INCIDENTS_MANAGE, INCIDENTS_READ, SERVICES_READ

router = APIRouter(prefix="/api/v1", tags=["support"])


def support_module(request: Request) -> SupportModule:
    module = getattr(request.app.state, "support_module", None)
    if not isinstance(module, SupportModule):
        raise Unavailable("Support is not available.", code="support.unavailable")
    return module


Module = Annotated[SupportModule, Depends(support_module)]
Reader = Annotated[Principal, require(INCIDENTS_READ)]
Manager = Annotated[Principal, require(INCIDENTS_MANAGE)]
IfMatch = Annotated[str | None, Header(alias="If-Match", max_length=32)]
Severity = Literal["minor", "major", "critical"]


def version_of(if_match: str | None) -> int | None:
    if if_match is None:
        return None
    try:
        return int(if_match.strip().removeprefix("W/").strip('"'))
    except ValueError as exc:
        raise ValidationFailed(
            "If-Match must be the incident version.", code="incident.invalid_version"
        ) from exc


class ServiceOut(BaseModel):
    id: str
    name: str


class IncidentUpdateOut(BaseModel):
    seq: int
    state: str
    severity: str
    message: str
    at: str
    author_user_id: str | None


class IncidentOut(BaseModel):
    id: UUID
    reference: str
    title: str
    summary: str
    severity: Severity
    state: Literal["investigating", "identified", "monitoring", "resolved"]
    source: str
    created_at: str
    updated_at: str
    resolved_at: str | None
    version: int
    services: list[ServiceOut]
    updates: list[IncidentUpdateOut]
    evidence: list[str]


class IncidentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    severity: Severity
    summary: str = Field(default="", max_length=4000)
    service_ids: list[str] = Field(default_factory=list, max_length=50)


class IncidentUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)
    state: Literal["investigating", "identified", "monitoring"] | None = None


class IncidentPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity: Severity | None = None
    service_ids: list[str] | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, min_length=3, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)


class IncidentResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(default="", max_length=4000)


async def _out(module: SupportModule, principal: Principal, view: IncidentView) -> IncidentOut:
    manager = await module.authorizer.is_allowed(principal, INCIDENTS_MANAGE)
    sees_services = manager or await module.authorizer.is_allowed(principal, SERVICES_READ)
    names = await module.service_names() if sees_services and view.service_ids else {}
    services = (
        [ServiceOut(id=s, name=names.get(s, s)) for s in view.service_ids if manager or s in names]
        if sees_services
        else []
    )
    return IncidentOut(
        id=view.id,
        reference=view.reference,
        title=view.title,
        summary=view.summary,
        severity=view.severity,
        state=view.state,
        source=view.source if manager else ("manual" if view.source == "manual" else "automatic"),
        created_at=view.created_at.isoformat(),
        updated_at=view.updated_at.isoformat(),
        resolved_at=view.resolved_at.isoformat() if view.resolved_at else None,
        version=view.version,
        services=services,
        updates=[
            IncidentUpdateOut(**{**u, "author_user_id": u["author_user_id"] if manager else None})
            for u in view.updates
        ],
        evidence=view.evidence if manager else [],
    )


@router.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(
    principal: Reader,
    module: Module,
    state: Annotated[
        Literal["open", "investigating", "identified", "monitoring", "resolved"] | None, Query()
    ] = None,
    service: Annotated[str | None, Query(max_length=64)] = None,
) -> list[IncidentOut]:
    if service is not None and not await module.authorizer.is_allowed(principal, SERVICES_READ):
        return []  # filtering by a service the viewer cannot see reveals nothing
    return [
        await _out(module, principal, v) for v in await module.incidents.list(state=state, service_id=service)
    ]


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
async def get_incident(principal: Reader, incident_id: UUID, module: Module) -> IncidentOut:
    return await _out(module, principal, await module.incidents.get(incident_id))


@router.post("/admin/incidents", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
async def create_incident(principal: Manager, body: IncidentIn, module: Module) -> IncidentOut:
    view, _ = await module.incidents.create(
        principal,
        title=body.title,
        severity=body.severity,
        summary=body.summary,
        service_ids=body.service_ids,
    )
    return await _out(module, principal, view)


@router.post("/admin/incidents/{incident_id}/updates", response_model=IncidentOut)
async def add_update(
    principal: Manager, incident_id: UUID, body: IncidentUpdateIn, module: Module, if_match: IfMatch = None
) -> IncidentOut:
    view = await module.incidents.update(
        principal, incident_id, message=body.message, state=body.state, if_match=version_of(if_match)
    )
    return await _out(module, principal, view)


@router.patch("/admin/incidents/{incident_id}", response_model=IncidentOut)
async def patch_incident(
    principal: Manager, incident_id: UUID, body: IncidentPatchIn, module: Module, if_match: IfMatch = None
) -> IncidentOut:
    view = await module.incidents.patch(
        principal,
        incident_id,
        severity=body.severity,
        service_ids=body.service_ids,
        title=body.title,
        summary=body.summary,
        if_match=version_of(if_match),
    )
    return await _out(module, principal, view)


@router.post("/admin/incidents/{incident_id}/resolve", response_model=IncidentOut)
async def resolve_incident(
    principal: Manager, incident_id: UUID, body: IncidentResolveIn, module: Module, if_match: IfMatch = None
) -> IncidentOut:
    view = await module.incidents.resolve(
        principal, incident_id, message=body.message, if_match=version_of(if_match)
    )
    return await _out(module, principal, view)
