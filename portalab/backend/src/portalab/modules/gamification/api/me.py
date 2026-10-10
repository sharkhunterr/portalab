"""Progression API (T010, T026, T028): own progression and history (the three values separately, level
derived), achievements, the catalog (hidden achievements stay hidden until unlocked), and another user's
progression only as their visibility (021) allows — otherwise 404, revealing nothing."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel

from portalab.capabilities.economy import (
    LeaderboardEntry,
    LeaderboardPeriod,
    LeaderboardView,
    Progress,
    Transaction,
)
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound, Unavailable
from portalab.core.time import utc_now
from portalab.core.visibility_port import Redacted
from portalab.modules.gamification.integrations import PROGRESSION
from portalab.modules.gamification.module import GamificationModule
from portalab.modules.gamification.permissions import READ
from portalab.modules.gamification.progression.level_up import level_up_summary

router = APIRouter(prefix="/api/v1", tags=["gamification"])
SELF = "users.self.manage"


def gamification_module(request: Request) -> GamificationModule:
    module = getattr(request.app.state, "gamification_module", None)
    if not isinstance(module, GamificationModule):
        raise Unavailable("Gamification is not available.", code="gamification.unavailable")
    return module


Module = Annotated[GamificationModule, Depends(gamification_module)]
Me = Annotated[Principal, require(SELF)]
Reader = Annotated[Principal, require(READ)]


class BoostOut(BaseModel):
    """#55: the member's gains boost in progress (``until``: the end of the boosts queued after it)."""

    factor: float
    gains: list[str]
    ends_at: datetime
    until: datetime


class ProgressionOut(BaseModel):
    user_id: UUID
    xp: int
    level: int
    level_floor: int
    next_level_at: int | None
    contribution: int
    coins: int
    reserved_coins: int
    achievements: int
    boost: BoostOut | None = None  # only on the member's own progression


class EconomyTransactionOut(BaseModel):
    id: UUID
    value: str
    delta: int
    kind: str
    source_kind: str
    rule_key: str | None
    rule_version: int | None
    reason: str | None
    reverses_transaction_id: UUID | None
    occurred_at: datetime


class EconomyTransactionPage(BaseModel):
    items: list[EconomyTransactionOut]
    next_cursor: str | None


def progression_out(progress: Progress) -> ProgressionOut:
    return ProgressionOut(
        user_id=progress.user_id,
        xp=progress.xp,
        level=progress.level,
        level_floor=progress.level_floor,
        next_level_at=progress.next_level_at,
        contribution=progress.contribution,
        coins=progress.coins,
        reserved_coins=progress.reserved,
        achievements=progress.achievements,
    )


def transaction_out(t: Transaction) -> EconomyTransactionOut:
    return EconomyTransactionOut(
        id=t.id,
        value=t.value,
        delta=t.delta,
        kind=t.kind,
        source_kind=t.source_kind,
        rule_key=t.rule_key,
        rule_version=t.rule_version,
        reason=t.reason,
        reverses_transaction_id=t.reverses_transaction_id,
        occurred_at=t.occurred_at,
    )


def _me(principal: Principal) -> UUID:
    user = principal.acting_for or principal.user_id
    assert user is not None
    return user


@router.get("/me/progression", response_model=ProgressionOut)
async def my_progression(principal: Me, module: Module) -> ProgressionOut:
    out = progression_out(await module.progression.progress(_me(principal)))
    boost = (await module.perks.state(_me(principal)))["boost"]
    out.boost = BoostOut.model_validate(boost) if boost else None
    return out


@router.get("/me/economy/transactions", response_model=EconomyTransactionPage)
async def my_transactions(
    principal: Me,
    module: Module,
    value: Literal["xp", "contribution", "coins"] | None = None,
    cursor: str | None = None,
) -> EconomyTransactionPage:
    page = await module.economy.history(_me(principal), value=value, cursor=cursor)
    return EconomyTransactionPage(
        items=[transaction_out(t) for t in page.items], next_cursor=page.next_cursor
    )


@router.get("/me/achievements")
async def my_achievements(principal: Me, module: Module) -> list[dict[str, Any]]:
    return await module.achievements.progress(_me(principal))


@router.get("/me/level-ups/{level}")
async def my_level_up(
    principal: Me,
    module: Module,
    level: Annotated[int, Path(ge=2, le=100_000)],
    since: Annotated[int | None, Query(ge=1, le=100_000)] = None,
) -> dict[str, Any]:
    """027: the level-up moment — the new level, the level rewards crossed, the achievements just
    unlocked and what they gave (own data only)."""
    return await level_up_summary(
        module.database,
        module.levels,
        module.achievements,
        module.config,
        _me(principal),
        level,
        since,
        clock=module.clock,
    )


@router.get("/achievements/catalog")
async def catalog(_: Reader, module: Module) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for definition in await module.achievements.definitions(utc_now(module.clock)):
        if definition.definition.hidden:
            out.append({"key": definition.key, "hidden": True})
            continue
        out.append(
            {
                "key": definition.key,
                "hidden": False,
                "label": definition.definition.label,
                "description": definition.definition.description,
                "icon": definition.definition.icon,
                "rewards": [r.model_dump() for r in definition.definition.rewards],
            }
        )
    return out


@router.get("/users/{user_id}/progression", response_model=ProgressionOut)
async def user_progression(principal: Reader, user_id: UUID, module: Module) -> ProgressionOut:
    progress = await module.progression.progress(user_id)
    shown = await module.visibility.filter(principal, user_id, PROGRESSION, None, progress)
    if isinstance(shown, Redacted):
        raise NotFound("This progression is not visible.", code="gamification.not_visible")
    return progression_out(progress)


# --- leaderboards (slice B, T037) -----------------------------------------------------------------------
class LeaderboardEntryOut(BaseModel):
    rank: int
    user_id: UUID
    display_name: str | None
    score: int
    me: bool
    change: int | None = None  # #66: places gained (> 0) or lost (< 0) since a day
    new: bool = False
    anonymous: bool = False  # #66: a private member — no name, no avatar, no profile


class LeaderboardOut(BaseModel):
    metric: str
    period: str
    computed_at: datetime | None
    entries: list[LeaderboardEntryOut]
    me: LeaderboardEntryOut | None


class LeaderboardPositionOut(BaseModel):
    metric: str
    period: str
    rank: int | None
    score: int | None


async def leaderboard_out(module: GamificationModule, view: LeaderboardView) -> LeaderboardOut:
    providers = module.capabilities.system_providers(DIRECTORY)
    directory = providers[0].provider if providers else None

    async def entry(e: LeaderboardEntry) -> LeaderboardEntryOut:
        summary = await directory.get_user_summary(e.user_id) if directory and not e.anonymous else None
        name = summary.display_name if summary and not summary.anonymized else None
        return LeaderboardEntryOut(
            rank=e.rank,
            user_id=e.user_id,
            display_name=name,
            score=e.score,
            me=e.me,
            change=e.change,
            new=e.new,
            anonymous=e.anonymous,
        )

    return LeaderboardOut(
        metric=view.metric,
        period=view.period,
        computed_at=view.computed_at,
        entries=[await entry(e) for e in view.entries],
        me=await entry(view.me) if view.me else None,
    )


@router.get("/leaderboards", response_model=list[str])
async def leaderboard_metrics(_: Reader, module: Module) -> list[str]:
    return list(module.leaderboards.metrics())


@router.get("/leaderboards/{metric}", response_model=LeaderboardOut)
async def leaderboard(
    principal: Reader,
    metric: str,
    module: Module,
    period: LeaderboardPeriod = "all",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> LeaderboardOut:
    return await leaderboard_out(
        module, await module.leaderboards.board(principal, metric, period, limit=limit)
    )


@router.get("/me/leaderboard-position", response_model=LeaderboardPositionOut)
async def my_position(
    principal: Me, module: Module, metric: str = "xp", period: LeaderboardPeriod = "all"
) -> LeaderboardPositionOut:
    view = await module.leaderboards.board(principal, metric, period, limit=1)
    return LeaderboardPositionOut(
        metric=metric,
        period=period,
        rank=view.me.rank if view.me else None,
        score=view.me.score if view.me else None,
    )


# --- quests (slice C, T039) -----------------------------------------------------------------------------
@router.get("/me/quests")
async def my_quests(principal: Me, module: Module) -> list[dict[str, Any]]:
    return await module.quests.mine(_me(principal))


@router.get("/quests/catalog")
async def quest_catalog(_: Reader, module: Module) -> list[dict[str, Any]]:
    return await module.quests.catalog()
