"""The requests module, for its routes — every route answers « unavailable » while the module is switched
off."""

from typing import Annotated

from fastapi import Depends, Request

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.requests.module import RequestsModule


async def requests_module(request: Request) -> RequestsModule:
    module = getattr(request.app.state, "requests_module", None)
    if not isinstance(module, RequestsModule) or not await module.enabled():
        raise Unavailable("The requests are not available.", code="requests.unavailable")
    return module


Module = Annotated[RequestsModule, Depends(requests_module)]
Reader = Annotated[Principal, require("media.read")]  # who reads the library may ask for a title
