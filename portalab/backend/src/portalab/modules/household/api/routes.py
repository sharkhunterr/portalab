"""Household routes (spec 032): the « Who's there? » picker and the switch, the household page (every member),
its management and the access requests (the master)."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.household.api.deps import household_module
from portalab.modules.household.module import HouseholdModule
from portalab.modules.household.rules import RestrictionSettings

router = APIRouter(prefix="/api/v1/household", tags=["household"])
Module = Annotated[HouseholdModule, Depends(household_module)]
SELF = "users.self.manage"
Kind = Literal["standard", "child", "custom"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HouseholdMemberTile(BaseModel):
    id: UUID
    display_name: str
    kind: Literal["owner", "standard", "child", "custom"]
    color: str
    has_avatar: bool
    has_pin: bool
    needs_pin: bool = False


class HouseholdSession(BaseModel):
    enabled: bool
    made: bool = False  # issue 445: a household made (a profile's, or its master's own)
    owner_id: UUID
    active_id: UUID | None
    must_choose: bool
    members: list[HouseholdMemberTile]


class HouseholdSwitchIn(_Strict):
    user_id: UUID
    pin: str | None = Field(default=None, max_length=6)


class HouseholdSwitchOut(BaseModel):
    active_id: UUID


class HouseholdFigures(BaseModel):
    xp: int
    level: int
    coins: int
    contribution: int


class HouseholdMemberOut(HouseholdMemberTile):
    progress: HouseholdFigures
    community_visible: bool
    restrictions: RestrictionSettings | None = None
    age: int | None = None  # from its birth date
    effective_age: int | None = None  # the age its titles are held to (None: no limit)
    bonus_minutes: int = 0  # issue 432: screen time given for today
    free_until: datetime | None = None  # no limits until then


class HouseholdOut(BaseModel):
    enabled: bool
    owner_id: UUID
    me: UUID | None
    can_manage: bool
    max_profiles: int
    # issue 478: the other countries whose age ratings count by the administrator's choice (a profile follows
    # them unless its master chooses its own)
    rating_countries: list[str] = []
    palette: list[str]  # the colours a profile may take
    totals: HouseholdFigures | None
    members: list[HouseholdMemberOut]
    economy: Literal["pot", "dispatch"] = "pot"  # issue 443: a common pot on the master, or dispatched


class HouseholdProfileIn(_Strict):
    display_name: str = Field(min_length=1, max_length=64)
    kind: Kind = "standard"
    color: str | None = Field(default=None, max_length=16)
    pin: str | None = Field(default=None, max_length=6)


class HouseholdProfileCreated(BaseModel):
    id: UUID


class HouseholdProfilePatch(_Strict):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    kind: Kind | None = None
    restrictions: RestrictionSettings | None = None
    community_visible: bool | None = None
    position: int | None = Field(default=None, ge=1, le=99)


class HouseholdPinIn(_Strict):
    pin: str | None = Field(default=None, max_length=6)
    current: str | None = Field(default=None, max_length=6)


class HouseholdEconomyLine(BaseModel):
    value: str
    delta: int
    kind: str
    source: str
    rule: str | None
    reason: str | None
    at: datetime


class AccessRequestOut(BaseModel):
    id: UUID
    profile_id: UUID
    profile_name: str
    kind: str
    subject_ref: str
    title: str
    rating: str | None
    note: str | None
    status: Literal["pending", "approved", "denied"]
    created_at: datetime
    decided_at: datetime | None
    expires_at: datetime | None


class ProfileActivityOut(BaseModel):
    last_seen_at: datetime | None
    economy: list[HouseholdEconomyLine]
    requests: list[AccessRequestOut]


class AccessAskIn(_Strict):
    kind: Literal["media"] = "media"
    ref: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    rating: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=300)


class AccessAskOut(BaseModel):
    id: UUID
    status: Literal["pending"]
    created: bool


class AccessDecisionIn(_Strict):
    approve: bool
    days: int | None = Field(default=None, ge=1, le=365)


@router.get("/session", response_model=HouseholdSession)
async def household_session(module: Module, principal: Principal = require(SELF)) -> HouseholdSession:
    return HouseholdSession.model_validate(await module.service.state(principal))


@router.post(
    "/switch",
    response_model=HouseholdSwitchOut,
    responses={403: {"description": "household.wrong_pin"}, 429: {"description": "household.pin_throttled"}},
)
async def switch_profile(
    body: HouseholdSwitchIn, module: Module, principal: Principal = require(SELF)
) -> HouseholdSwitchOut:
    return HouseholdSwitchOut.model_validate(await module.service.switch(principal, body.user_id, body.pin))


@router.get("", response_model=HouseholdOut)
async def household(module: Module, principal: Principal = require(SELF)) -> HouseholdOut:
    return HouseholdOut.model_validate(await module.service.overview(principal))


@router.post(
    "/profiles",
    response_model=HouseholdProfileCreated,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "household.limit"}},
)
async def create_profile(
    body: HouseholdProfileIn, module: Module, principal: Principal = require(SELF)
) -> HouseholdProfileCreated:
    created = await module.service.create(
        principal, display_name=body.display_name, kind=body.kind, color=body.color, pin=body.pin
    )
    return HouseholdProfileCreated.model_validate(created)


@router.patch("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def change_profile(
    profile_id: UUID, body: HouseholdProfilePatch, module: Module, principal: Principal = require(SELF)
) -> Response:
    await module.service.change(
        principal,
        profile_id,
        display_name=body.display_name,
        color=body.color,
        kind=body.kind,
        restrictions=body.restrictions,
        community_visible=body.community_visible,
        position=body.position,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: UUID, module: Module, principal: Principal = require(SELF)) -> Response:
    await module.service.remove(principal, profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/members/{member_id}/pin", status_code=status.HTTP_204_NO_CONTENT)
async def set_pin(
    member_id: UUID, body: HouseholdPinIn, module: Module, principal: Principal = require(SELF)
) -> Response:
    await module.service.set_pin(principal, member_id, body.pin, body.current)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class HouseholdMinutesIn(_Strict):
    minutes: int = Field(ge=1, le=120)  # issue 432: 15, 30, 60 or 120 more today


class HouseholdFreeIn(_Strict):
    minutes: int | None = Field(default=None, ge=15, le=1440)  # issue 432: none — the limits back now


class HouseholdEconomyIn(_Strict):
    economy: Literal["pot", "dispatch"]


@router.post("/made", status_code=status.HTTP_204_NO_CONTENT)
async def make_household(
    body: HouseholdEconomyIn, module: Module, principal: Principal = require(SELF)
) -> Response:
    """Issue 445: the master makes its household with its economy (once) — « My household » appears."""
    await module.service.make(principal, body.economy)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/made", status_code=status.HTTP_204_NO_CONTENT)
async def unmake_household(module: Module, principal: Principal = require(SELF)) -> Response:
    """Issue 445: a household without profiles undone — « My household » disappears."""
    await module.service.unmake(principal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/economy", status_code=status.HTTP_204_NO_CONTENT)
async def set_economy(
    body: HouseholdEconomyIn, module: Module, principal: Principal = require(SELF)
) -> Response:
    """Issue 443: the master chooses its household's economy — a common pot on its account (its profiles kept
    out of the community) or dispatched profiles (each its own wallet, in the community)."""
    await module.service.set_economy(principal, body.economy)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/profiles/{profile_id}/minutes", status_code=status.HTTP_204_NO_CONTENT)
async def give_minutes(
    profile_id: UUID, body: HouseholdMinutesIn, module: Module, principal: Principal = require(SELF)
) -> Response:
    """Issue 432: screen time more for a profile, today only (its master)."""
    await module.service.give_minutes(principal, profile_id, body.minutes)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/profiles/{profile_id}/free", status_code=status.HTTP_204_NO_CONTENT)
async def free_profile(
    profile_id: UUID, body: HouseholdFreeIn, module: Module, principal: Principal = require(SELF)
) -> Response:
    """Issue 432: a profile without limits for a while, or its limits back now (its master)."""
    await module.service.free(principal, profile_id, body.minutes)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/profiles/{profile_id}/activity", response_model=ProfileActivityOut)
async def profile_activity(
    profile_id: UUID, module: Module, principal: Principal = require(SELF)
) -> ProfileActivityOut:
    return ProfileActivityOut.model_validate(await module.service.activity(principal, profile_id))


@router.get("/requests", response_model=list[AccessRequestOut])
async def access_requests(module: Module, principal: Principal = require(SELF)) -> list[AccessRequestOut]:
    return [AccessRequestOut.model_validate(r) for r in await module.service.requests(principal)]


@router.post("/requests", response_model=AccessAskOut)
async def ask_access(body: AccessAskIn, module: Module, principal: Principal = require(SELF)) -> AccessAskOut:
    asked = await module.service.ask(
        principal, kind=body.kind, ref=body.ref, title=body.title, rating=body.rating, note=body.note
    )
    return AccessAskOut.model_validate(asked)


@router.post("/requests/{request_id}/decision", status_code=status.HTTP_204_NO_CONTENT)
async def decide_access(
    request_id: UUID, body: AccessDecisionIn, module: Module, principal: Principal = require(SELF)
) -> Response:
    await module.service.decide(principal, request_id, approve=body.approve, days=body.days)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
