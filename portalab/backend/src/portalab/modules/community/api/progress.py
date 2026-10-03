"""Community achievements and quests API (T020, slice C): ``community.read``; content and rules from 013.
Another member's achievements follow their ``progression`` visibility (404 revealing nothing otherwise)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from portalab.modules.community.api.public import Module
from portalab.modules.community.permissions import READ

router = APIRouter(prefix="/api/v1", tags=["community"])
Reader = Annotated[Principal, require(READ)]


class CommunityCatalogOut(BaseModel):
    state: str
    items: list[dict[str, Any]]


@router.get("/community/achievements", response_model=CommunityCatalogOut)
async def community_achievements(
    principal: Reader, module: Module, member: UUID | None = None
) -> CommunityCatalogOut:
    me = principal.acting_for or principal.user_id
    if member is None or member == me:
        view = await module.achievements.mine(principal)
    else:
        found = await module.members.get(principal, member)
        other = await module.achievements.of(principal, member) if found is not None else None
        if other is None:
            raise NotFound("No such member.", code="community.member_not_found")
        view = other
    return CommunityCatalogOut(state=view.state, items=view.items)


@router.get("/community/quests", response_model=CommunityCatalogOut)
async def community_quests(principal: Reader, module: Module) -> CommunityCatalogOut:
    view = await module.quests.mine(principal)
    return CommunityCatalogOut(state=view.state, items=view.items)
