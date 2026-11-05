"""Community read API (T008, T010, T012): the members directory, profiles with independent sections, the
activity feed and discovery shelves. ``require(community.read)`` first, then each owner's visibility (021):
a profile with nothing visible to this viewer is a 404 that reveals nothing."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from portalab.capabilities.search.fts import decode_cursor, encode_cursor
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, Unavailable
from portalab.modules.community.module import CommunityModule
from portalab.modules.community.permissions import READ
from portalab.modules.community.profiles.assembler import AssembledSection

router = APIRouter(prefix="/api/v1", tags=["community"])


def community_module(request: Request) -> CommunityModule:
    module = getattr(request.app.state, "community_module", None)
    if not isinstance(module, CommunityModule):
        raise Unavailable("Community is not available.", code="community.unavailable")
    return module


Module = Annotated[CommunityModule, Depends(community_module)]
Reader = Annotated[Principal, require(READ)]


class MemberLookOut(BaseModel):
    """#127: what a member wears beside their name across the community."""

    frame: str | None = None  # the avatar frame
    name: str | None = None  # the name's style (font and effect)


def look_out(look: dict[str, Any] | None) -> MemberLookOut | None:
    return MemberLookOut(frame=look.get("frame"), name=look.get("name")) if look else None


class CommunityMemberOut(BaseModel):
    id: UUID
    display_name: str
    joined_at: datetime
    look: MemberLookOut | None = None  # #127


class CommunityMemberPage(BaseModel):
    items: list[CommunityMemberOut]
    next_cursor: str | None
    anonymous: int = 0  # issue 347: on the last page, how many anonymous members close the directory


class CommunitySectionOut(BaseModel):
    key: str
    owner: str
    label_key: str
    state: str
    data: dict[str, Any]


class CommunityProfileOut(BaseModel):
    id: UUID
    display_name: str | None
    sections: list[CommunitySectionOut]
    looks: dict[str, Any] = Field(default_factory=dict)  # 027: banner, avatar frame, film backdrop


class CommunityFeedItemOut(BaseModel):
    id: UUID
    actor_id: UUID
    actor_name: str | None
    anonymous: bool = False  # issue 120: the actor keeps their progression to themselves
    look: MemberLookOut | None = None  # #127: the actor's frame and name style (none when anonymous)
    kind: str
    text_key: str
    params: dict[str, Any]
    subject_ref: str | None
    source_event_id: UUID
    occurred_at: datetime


class CommunityFeedPage(BaseModel):
    items: list[CommunityFeedItemOut]
    next_cursor: str | None


class CommunityShelfInfo(BaseModel):
    key: str
    label_key: str
    empty_action: str | None


class CommunityShelfOut(CommunityShelfInfo):
    state: str
    items: list[dict[str, Any]]


def section_out(section: AssembledSection) -> CommunitySectionOut:
    return CommunitySectionOut(
        key=section.key,
        owner=section.owner,
        label_key=section.label_key,
        state=section.result.state,
        data=dict(section.result.data),
    )


@router.get("/community/members", response_model=CommunityMemberPage)
async def members(
    principal: Reader,
    module: Module,
    q: Annotated[str | None, Query(max_length=64)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> CommunityMemberPage:
    page = await module.members.page(principal, query=q, offset=decode_cursor(cursor), limit=limit)
    return CommunityMemberPage(
        items=[
            CommunityMemberOut(
                id=m.id,
                display_name=m.display_name,
                joined_at=m.joined_at,
                look=look_out(await module.look_of(m.id)),
            )
            for m in page.items
        ],
        next_cursor=encode_cursor(page.next_offset) if page.next_offset is not None else None,
        anonymous=page.anonymous,
    )


async def _visible_member(module: CommunityModule, principal: Principal, member: UUID) -> str | None:
    found = await module.members.get(principal, member)
    if found is None:
        raise NotFound("No such member.", code="community.member_not_found")
    name, listed = found
    return name if listed else None


@router.get("/community/members/{member_id}", response_model=CommunityProfileOut)
async def profile(principal: Reader, member_id: UUID, module: Module) -> CommunityProfileOut:
    name = await _visible_member(module, principal, member_id)
    sections = await module.profiles.profile(principal, member_id)
    if not sections:
        raise NotFound("No such member.", code="community.member_not_found")
    return CommunityProfileOut(
        id=member_id,
        display_name=name if any(s.key == "identity" for s in sections) else None,
        sections=[section_out(s) for s in sections],
        looks=await module.looks_of(member_id),
    )


@router.get("/community/members/{member_id}/sections/{name}", response_model=CommunitySectionOut)
async def profile_section(
    principal: Reader, member_id: UUID, name: str, module: Module
) -> CommunitySectionOut:
    await _visible_member(module, principal, member_id)
    section = await module.profiles.section(principal, member_id, name)
    if section is None:
        raise NotFound("No such section.", code="community.section_not_found")
    return section_out(section)


@router.get("/community/feed", response_model=CommunityFeedPage)
async def feed(
    principal: Reader,
    module: Module,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> CommunityFeedPage:
    items, next_cursor = await module.feed.page(principal, cursor=cursor, limit=limit)
    return CommunityFeedPage(
        items=[
            CommunityFeedItemOut(
                id=i.id,
                actor_id=i.actor_id,
                actor_name=i.actor_name,
                anonymous=i.anonymous,
                look=None if i.anonymous else look_out(await module.look_of(i.actor_id)),
                kind=i.kind,
                text_key=i.text_key,
                params=i.params,
                subject_ref=i.subject_ref,
                source_event_id=i.source_event_id,
                occurred_at=i.occurred_at,
            )
            for i in items
        ],
        next_cursor=next_cursor,
    )


@router.get("/community/discovery", response_model=list[CommunityShelfInfo])
async def shelves(principal: Reader, module: Module) -> list[CommunityShelfInfo]:
    return [
        CommunityShelfInfo(key=s.key, label_key=s.label_key, empty_action=s.empty_action)
        for s in module.shelves.all()
    ]


@router.get("/community/discovery/{shelf}", response_model=CommunityShelfOut)
async def shelf(principal: Reader, shelf: str, module: Module) -> CommunityShelfOut:
    found = module.shelves.get(shelf)
    if found is None:
        raise NotFound("No such shelf.", code="community.shelf_not_found")
    try:
        items = [dict(i) for i in await found.provider(principal, module.config.discovery_shelf_size)]
        for item in items:  # #127: a member on a shelf wears their frame and name style there too
            who = item.get("actor_id") or (item.get("id") if item.get("display_name") else None)
            if who and not item.get("anonymous"):
                look = await module.look_of(UUID(str(who)))
                item["look"] = look if any(look.values()) else None
        state = "available" if items else "no-data"
    except Exception:  # a failing shelf degrades alone
        items, state = [], "unavailable"
    return CommunityShelfOut(
        key=found.key, label_key=found.label_key, empty_action=found.empty_action, state=state, items=items
    )
