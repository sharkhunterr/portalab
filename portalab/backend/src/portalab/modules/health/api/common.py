"""Shared API helpers: module lookup and the caller's permission tier (enforced server side)."""

from typing import Annotated

from fastapi import Depends, Request

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.errors import Unavailable
from portalab.modules.health.detail.assembler import Tier
from portalab.modules.health.module import HealthModule
from portalab.modules.health.permissions import INFRASTRUCTURE_READ, SERVICES_MANAGE


def health_module(request: Request) -> HealthModule:
    module = getattr(request.app.state, "health_module", None)
    if not isinstance(module, HealthModule):
        raise Unavailable("Service health is not available.", code="health.unavailable")
    return module


Module = Annotated[HealthModule, Depends(health_module)]


async def tier_of(request: Request, principal: Principal) -> Tier:
    authorizer: Authorizer = request.app.state.authorizer
    return Tier(
        infrastructure=await authorizer.is_allowed(principal, INFRASTRUCTURE_READ, None),
        manage=await authorizer.is_allowed(principal, SERVICES_MANAGE, None),
    )
