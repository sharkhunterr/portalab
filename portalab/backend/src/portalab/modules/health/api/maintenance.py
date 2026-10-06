"""Maintenance API (T016): read for ``services.read``; schedule/reschedule/cancel for ``services.manage``
(cancel is sensitive and audited)."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.health.api.common import Module
from portalab.modules.health.permissions import SERVICES_MANAGE, SERVICES_READ

router = APIRouter(prefix="/api/v1", tags=["health"])


class WindowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    starts_at: datetime
    ends_at: datetime
    reference_time_zone: str | None = Field(default=None, max_length=64)
    banner: bool = False  # 027: also a banner across the portal


class WindowPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    reference_time_zone: str | None = Field(default=None, max_length=64)
    banner: bool | None = None


@router.get("/maintenance")
async def list_windows(
    _: Annotated[Principal, require(SERVICES_READ)], module: Module, include_past: bool = False
) -> dict[str, Any]:
    return {"items": await module.maintenance.windows(include_past=include_past)}


@router.get("/services/{service_id}/maintenance")
async def service_windows(
    _: Annotated[Principal, require(SERVICES_READ)], service_id: str, module: Module
) -> dict[str, Any]:
    return {"items": await module.maintenance.windows(service_id=service_id, include_past=True)}


@router.post("/maintenance", status_code=status.HTTP_201_CREATED)
async def schedule(
    principal: Annotated[Principal, require(SERVICES_MANAGE)], body: WindowIn, module: Module
) -> dict[str, Any]:
    return await module.maintenance.create(principal, **body.model_dump())


@router.patch("/maintenance/{window_id}")
async def reschedule(
    principal: Annotated[Principal, require(SERVICES_MANAGE)],
    window_id: UUID,
    body: WindowPatch,
    module: Module,
) -> dict[str, Any]:
    return await module.maintenance.reschedule(principal, window_id, **body.model_dump(exclude_none=True))


@router.delete("/maintenance/{window_id}")
async def cancel(
    principal: Annotated[Principal, require(SERVICES_MANAGE)], window_id: UUID, module: Module
) -> dict[str, Any]:
    return await module.maintenance.cancel(principal, window_id)
