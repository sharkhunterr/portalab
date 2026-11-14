"""The household module as a route dependency: unavailable while switched off in the module manager."""

from typing import Annotated

from fastapi import Depends, Request

from portalab.core.errors import Unavailable
from portalab.modules.household.module import HouseholdModule


async def household_module(request: Request) -> HouseholdModule:
    module = getattr(request.app.state, "household_module", None)
    if not isinstance(module, HouseholdModule) or not await module.enabled():
        raise Unavailable("Profiles are switched off on this portal.", code="household.disabled")
    return module


Module = Annotated[HouseholdModule, Depends(household_module)]
