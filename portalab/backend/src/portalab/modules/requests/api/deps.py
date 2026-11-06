"""The requests module and its principals, for its routes — every route answers « unavailable » while the
module is switched off."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.requests.module import RequestsModule
from portalab.modules.requests.permissions import ASK, MANAGE
from portalab.modules.requests.service import RequestNotFound


async def requests_module(request: Request) -> RequestsModule:
    module = getattr(request.app.state, "requests_module", None)
    if not isinstance(module, RequestsModule) or not await module.enabled():
        raise Unavailable("The requests are not available.", code="requests.unavailable")
    return module


Module = Annotated[RequestsModule, Depends(requests_module)]
Member = Annotated[Principal, require(ASK)]
Manager = Annotated[Principal, require(MANAGE)]


def me(principal: Principal) -> UUID:
    user = principal.acting_for or principal.user_id
    if user is None:
        raise RequestNotFound("No member.")
    return user
