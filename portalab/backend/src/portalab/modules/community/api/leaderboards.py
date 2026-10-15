"""Community leaderboards API (T018, slice B): ``community.read``, then everything is delegated to 013 —
metrics, periods, ranking, opt-out and visibility. ``unavailable`` when 013 is down, never an error page."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from portalab.capabilities.economy import LeaderboardPeriod
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.community.api.public import MemberLookOut, Module, look_out
from portalab.modules.community.leaderboards.view import BoardView, RankedMember
from portalab.modules.community.permissions import READ

router = APIRouter(prefix="/api/v1", tags=["community"])
Reader = Annotated[Principal, require(READ)]


class CommunityRankOut(BaseModel):
    rank: int
    user_id: UUID
    display_name: str | None
    score: int
    me: bool
    change: int | None = None  # #66: places gained (> 0) or lost (< 0) since a day
    new: bool = False
    anonymous: bool = False  # #66: a private member — no name, no avatar, no profile
    look: MemberLookOut | None = None  # #127: their avatar frame and name style


class CommunityLeaderboardOut(BaseModel):
    metric: str
    period: str
    state: str
    computed_at: datetime | None
    entries: list[CommunityRankOut]
    me: CommunityRankOut | None


class CommunityPositionOut(BaseModel):
    metric: str
    period: str
    state: str
    rank: int | None
    score: int | None


def rank_out(member: RankedMember) -> CommunityRankOut:
    return CommunityRankOut(
        rank=member.rank,
        user_id=member.user_id,
        display_name=member.display_name,
        score=member.score,
        me=member.me,
        change=member.change,
        new=member.new,
        anonymous=member.anonymous,
        look=look_out(member.look),
    )


def board_out(view: BoardView) -> CommunityLeaderboardOut:
    return CommunityLeaderboardOut(
        metric=view.metric,
        period=view.period,
        state=view.state,
        computed_at=view.computed_at,
        entries=[rank_out(e) for e in view.entries],
        me=rank_out(view.me) if view.me else None,
    )


@router.get("/community/leaderboards", response_model=list[str])
async def community_metrics(_: Reader, module: Module) -> list[str]:
    return module.leaderboards.metrics()


@router.get("/community/leaderboards/{metric}", response_model=CommunityLeaderboardOut)
async def community_leaderboard(
    principal: Reader,
    metric: str,
    module: Module,
    period: LeaderboardPeriod = "all",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CommunityLeaderboardOut:
    return board_out(await module.leaderboards.board(principal, metric, period, limit=limit))


@router.get("/community/me/position", response_model=CommunityPositionOut)
async def community_position(
    principal: Reader, module: Module, metric: str = "xp", period: LeaderboardPeriod = "all"
) -> CommunityPositionOut:
    view = await module.leaderboards.board(principal, metric, period, limit=1)
    return CommunityPositionOut(
        metric=metric,
        period=period,
        state=view.state,
        rank=view.me.rank if view.me else None,
        score=view.me.score if view.me else None,
    )
