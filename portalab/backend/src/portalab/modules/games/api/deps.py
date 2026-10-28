"""The games module and its principals, for its routes."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.games.common import GameNotFound
from portalab.modules.games.module import GamesModule
from portalab.modules.games.permissions import MANAGE, PLAY


def games_module(request: Request) -> GamesModule:
    module = getattr(request.app.state, "games_module", None)
    if not isinstance(module, GamesModule):
        raise Unavailable("The games are not available.", code="games.unavailable")
    return module


Module = Annotated[GamesModule, Depends(games_module)]
Player = Annotated[Principal, require(PLAY)]
Manager = Annotated[Principal, require(MANAGE)]


def me(principal: Principal) -> UUID:
    user = principal.acting_for or principal.user_id
    if user is None:
        raise GameNotFound("No member.")
    return user
