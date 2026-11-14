"""The retro module as a route dependency: unavailable while switched off in the module manager."""

from typing import Annotated

from fastapi import Depends, Request

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.retro.module import RetroModule
from portalab.modules.retro.permissions import PLAY


async def retro_module(request: Request) -> RetroModule:
    module = getattr(request.app.state, "retro_module", None)
    if not isinstance(module, RetroModule) or not await module.enabled():
        raise Unavailable("Retro play is switched off on this portal.", code="retro.disabled")
    return module


Module = Annotated[RetroModule, Depends(retro_module)]
Player = Annotated[Principal, require(PLAY)]
