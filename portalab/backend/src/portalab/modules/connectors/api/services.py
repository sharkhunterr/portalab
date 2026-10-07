"""Connectors API (T013, T016, T019): catalog, services, state changes, connection tests, discovery.

Secrets are write-only: requests may set them, responses only say which ones are set.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.errors import Unavailable
from portalab.modules.connectors.module import ConnectorsModule
from portalab.modules.connectors.permissions import (
    CONNECTORS_MANAGE,
    INFRASTRUCTURE_READ,
    SERVICES_MANAGE,
    SERVICES_READ,
)
from portalab.modules.connectors.services.manager import ServiceView
from portalab.modules.connectors.services.tester import as_dict

router = APIRouter(prefix="/api/v1", tags=["connectors"])


def connectors_module(request: Request) -> ConnectorsModule:
    module = getattr(request.app.state, "connectors_module", None)
    if not isinstance(module, ConnectorsModule):
        raise Unavailable("Connectors are not available.", code="connectors.unavailable")
    return module


Module = Annotated[ConnectorsModule, Depends(connectors_module)]
Name = Annotated[str, Field(min_length=1, max_length=128)]


class ServiceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connector: str = Field(min_length=1, max_length=64)
    name: Name
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)
    sync_interval_seconds: int | None = Field(default=None, ge=60, le=7 * 86400)


class CapabilityPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=10_000)


class ServicePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    config: dict[str, Any] | None = None
    secrets: dict[str, str | None] | None = None  # null or "" clears one secret
    sync_interval_seconds: int | None = Field(default=None, ge=0, le=7 * 86400)
    capabilities: dict[str, CapabilityPatch] | None = None
    # 027: where members open the service ("" clears it)
    public_url: str | None = Field(default=None, max_length=512, pattern=r"^(https?://[^\s]+)?$")
    # 027: how much it matters, and when its outage becomes an incident (-1: the importance's default)
    importance: Literal["critical", "major", "minor", "internal"] | None = None
    incident_after_minutes: int | None = Field(default=None, ge=-1, le=10_080)
    incident_auto_resolve: bool | None = None


class TestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: dict[str, Any] | None = None
    secrets: dict[str, str] | None = None


class DraftTestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)


class DiscoverIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    targets: list[Annotated[str, Field(min_length=1, max_length=512)]] = Field(min_length=1, max_length=32)


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)


async def may_see_details(request: Request, principal: Principal) -> bool:
    """Configuration and diagnostics are infrastructure details (FR-030): ``services.read`` alone shows a
    service's name and state; ``services.manage`` or ``infrastructure.read`` also shows its configuration."""
    authorizer: Authorizer = request.app.state.authorizer
    for permission in (SERVICES_MANAGE, INFRASTRUCTURE_READ):
        if await authorizer.is_allowed(principal, permission, None):
            return True
    return False


def service_out(view: ServiceView, *, details: bool = True) -> dict[str, Any]:
    if not details:
        return {
            "id": str(view.id),
            "connector": view.connector_key,
            "name": view.name,
            "state": view.state,
            "display_state": view.display_state,
            "health": view.health,
            "historical": view.historical,
            "stale": view.stale,
            "sync": {"status": view.sync["status"], "last_success_at": view.sync["last_success_at"]},
        }
    return {
        "id": str(view.id),
        "connector": view.connector_key,
        "name": view.name,
        "config": dict(view.config),
        "secrets_set": view.secrets_set,
        "state": view.state,
        "display_state": view.display_state,
        "state_reason": view.state_reason,
        "state_changed_at": view.state_changed_at.isoformat(),
        "health": view.health,
        "historical": view.historical,
        "stale": view.stale,
        "sync_interval_seconds": view.sync_interval_seconds,
        "public_url": view.public_url,
        "importance": view.importance,
        "incident_after_minutes": view.incident_after_minutes,
        "incident_auto_resolve": view.incident_auto_resolve,
        "capabilities": view.capabilities,
        "sync": view.sync,
        "created_at": view.created_at.isoformat(),
        "updated_at": view.updated_at.isoformat(),
    }


def _patches(items: Mapping[str, CapabilityPatch] | None) -> dict[str, dict[str, Any]] | None:
    if items is None:
        return None
    return {key: value.model_dump(exclude_none=True) for key, value in items.items()}


@router.get("/connectors")
async def list_connectors(_: Annotated[Principal, require(SERVICES_READ)], module: Module) -> dict[str, Any]:
    return {"items": module.manager.catalog()}


@router.get("/services")
async def list_services(
    principal: Annotated[Principal, require(SERVICES_READ)], request: Request, module: Module
) -> dict[str, Any]:
    details = await may_see_details(request, principal)
    return {"items": [service_out(view, details=details) for view in await module.manager.list()]}


@router.get("/services/{service_id}")
async def get_service(
    principal: Annotated[Principal, require(SERVICES_READ)],
    service_id: UUID,
    request: Request,
    module: Module,
) -> dict[str, Any]:
    view = await module.manager.get(service_id)
    return service_out(view, details=await may_see_details(request, principal))


@router.post("/services", status_code=status.HTTP_201_CREATED)
async def configure_service(
    principal: Annotated[Principal, require(SERVICES_MANAGE)], body: ServiceIn, module: Module
) -> dict[str, Any]:
    service_id = await module.manager.configure(
        principal,
        connector_key=body.connector,
        name=body.name,
        config=body.config,
        secrets=dict(body.secrets),
        sync_interval_seconds=body.sync_interval_seconds,
    )
    return service_out(await module.manager.get(service_id))


@router.patch("/services/{service_id}")
async def update_service(
    principal: Annotated[Principal, require(SERVICES_MANAGE)],
    service_id: UUID,
    body: ServicePatch,
    module: Module,
) -> dict[str, Any]:
    view = await module.manager.update(
        principal,
        service_id,
        name=body.name,
        config=body.config,
        secrets=body.secrets,
        sync_interval_seconds=body.sync_interval_seconds,
        capabilities=_patches(body.capabilities),
        public_url=body.public_url,
        importance=body.importance,
        incident_after_minutes=body.incident_after_minutes,
        incident_auto_resolve=body.incident_auto_resolve,
    )
    return service_out(view)


@router.post("/services/{service_id}/test")
async def test_service(
    _: Annotated[Principal, require(SERVICES_MANAGE)],
    service_id: UUID,
    module: Module,
    body: TestIn | None = None,
) -> dict[str, Any]:
    draft = body or TestIn()
    return as_dict(await module.tester.test_service(service_id, config=draft.config, secrets=draft.secrets))


@router.post("/connectors/{key}/test")
async def test_draft(
    _: Annotated[Principal, require(SERVICES_MANAGE)], key: str, body: DraftTestIn, module: Module
) -> dict[str, Any]:
    return as_dict(await module.tester.test_draft(key, body.config, body.secrets))


@router.post("/services/{service_id}/enable")
async def enable_service(
    principal: Annotated[Principal, require(CONNECTORS_MANAGE)], service_id: UUID, module: Module
) -> dict[str, Any]:
    return service_out(await module.manager.enable(principal, service_id))


@router.post("/services/{service_id}/disable")
async def disable_service(
    principal: Annotated[Principal, require(CONNECTORS_MANAGE)], service_id: UUID, module: Module
) -> dict[str, Any]:
    return service_out(await module.manager.disable(principal, service_id))


@router.post("/services/{service_id}/disconnect")
async def disconnect_service(
    principal: Annotated[Principal, require(CONNECTORS_MANAGE)], service_id: UUID, module: Module
) -> dict[str, Any]:
    return service_out(await module.manager.disconnect(principal, service_id))


@router.post("/connectors/{key}/discover")
async def discover(
    principal: Annotated[Principal, require(SERVICES_MANAGE)], key: str, body: DiscoverIn, module: Module
) -> dict[str, Any]:
    return {"items": await module.discovery.discover(principal, key, body.targets)}


@router.get("/discovery")
async def list_candidates(
    _: Annotated[Principal, require(SERVICES_MANAGE)], module: Module, connector: str | None = None
) -> dict[str, Any]:
    return {"items": await module.discovery.list(connector)}


@router.post("/discovery/{candidate_id}/confirm", status_code=status.HTTP_201_CREATED)
async def confirm_candidate(
    principal: Annotated[Principal, require(SERVICES_MANAGE)],
    candidate_id: UUID,
    body: ConfirmIn,
    module: Module,
) -> dict[str, Any]:
    service_id = await module.discovery.confirm(
        principal, candidate_id, name=body.name, config=body.config, secrets=dict(body.secrets)
    )
    return service_out(await module.manager.get(service_id))


@router.post("/discovery/{candidate_id}/decline")
async def decline_candidate(
    principal: Annotated[Principal, require(SERVICES_MANAGE)], candidate_id: UUID, module: Module
) -> dict[str, Any]:
    return await module.discovery.decline(principal, candidate_id)
