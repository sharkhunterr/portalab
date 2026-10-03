"""First-party modules (T029): ``modules.manage`` — list with dependencies, enable/disable (020 toggles;
a disable with dependents needs the cascade flag)."""

from typing import Annotated, Any

from fastapi import APIRouter
from pydantic import BaseModel

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.plugins.api.admin import Module
from portalab.modules.plugins.permissions import MODULES

router = APIRouter(prefix="/api/v1", tags=["modules-admin"])
Manager = Annotated[Principal, require(MODULES)]


class ModuleToggleIn(BaseModel):
    key: str
    enabled: bool
    cascade: bool = False


class ModuleCascadeIn(BaseModel):
    cascade: bool = False


@router.get("/admin/modules")
async def list_modules(_: Manager, module: Module) -> list[dict[str, Any]]:
    return await module.modules.states()


@router.put("/admin/modules")
async def put_module(principal: Manager, body: ModuleToggleIn, module: Module) -> dict[str, Any]:
    changed = await module.modules.set(principal, body.key, body.enabled, cascade=body.cascade)
    return {"changed": changed, "enabled": body.enabled}


@router.post("/admin/modules/{key}/enable")
async def enable_module(principal: Manager, key: str, module: Module) -> dict[str, Any]:
    return {"changed": await module.modules.set(principal, key, True), "enabled": True}


@router.post("/admin/modules/{key}/disable")
async def disable_module(
    principal: Manager, key: str, body: ModuleCascadeIn, module: Module
) -> dict[str, Any]:
    return {
        "changed": await module.modules.set(principal, key, False, cascade=body.cascade),
        "enabled": False,
    }
