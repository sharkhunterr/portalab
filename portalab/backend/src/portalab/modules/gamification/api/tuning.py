"""Gamification tuning (027): what the administration pages need besides raw rules — the actions that can
be rewarded (event types and their rewardable attributes), play streaks, level rewards and how members
progress over time (daily gains, the members who progress most, where the gains come from)."""

import types
from datetime import timedelta
from typing import Annotated, Any, Literal, Union, get_args, get_origin
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, cast, distinct, func, select

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.core.time import utc_now
from portalab.modules.gamification.api.me import Me, Module, _me
from portalab.modules.gamification.events import OWN_TYPES
from portalab.modules.gamification.models import LedgerTransaction
from portalab.modules.gamification.permissions import MANAGE
from portalab.modules.gamification.progression.sources import since_days
from portalab.modules.gamification.progression.sources import sources as gain_sources
from portalab.modules.gamification.settings import SETTINGS
from portalab.modules.gamification.streaks.level_rewards import LevelReward, parse_rewards
from portalab.modules.gamification.streaks.service import PaceConfig, StreakConfig, parse_pace, parse_streak

router = APIRouter(prefix="/api/v1", tags=["gamification-admin"])
Manager = Annotated[Principal, require(MANAGE)]
NUMERIC = (int, float)


def _numeric(annotation: Any) -> bool:
    if annotation in NUMERIC:
        return True
    if get_origin(annotation) in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        return bool(args) and all(a in NUMERIC for a in args)
    return False


class EventFieldOut(BaseModel):
    name: str
    numeric: bool


class EventTypeOut(BaseModel):
    name: str
    owner: str
    fields: list[EventFieldOut]


@router.get("/admin/gamification/event-types", response_model=list[EventTypeOut])
async def event_types(_: Manager, module: Module) -> list[EventTypeOut]:
    """Every action a rule may reward, with the attributes a rule may test or count."""
    out: list[EventTypeOut] = []
    for event_type in module.event_types.all():
        if event_type.name in OWN_TYPES:
            continue
        schema_fields = event_type.schema.model_fields if event_type.schema else {}
        fields = [
            EventFieldOut(
                name=name,
                numeric=_numeric(schema_fields[name].annotation) if name in schema_fields else False,
            )
            for name in sorted(event_type.rewardable)
        ]
        out.append(EventTypeOut(name=event_type.name, owner=event_type.owner, fields=fields))
    return sorted(out, key=lambda t: t.name)


async def _write(module: Any, principal: Principal, attribute: str, value: Any, reason: str) -> None:
    providers = module.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if not providers:
        raise Unavailable("Configuration is not available.", code="admin.unavailable")
    await providers[0].provider.set_global(principal, SETTINGS[attribute], value, reason=reason)
    await module.refresh_config()


@router.get("/admin/gamification/streak", response_model=StreakConfig)
async def get_streak(_: Manager, module: Module) -> StreakConfig:
    return parse_streak(module.config.streak)


@router.put("/admin/gamification/streak", response_model=StreakConfig)
async def put_streak(principal: Manager, body: StreakConfig, module: Module) -> StreakConfig:
    tiers = sorted({t.days: t for t in body.tiers}.values(), key=lambda t: t.days)
    clean = body.model_copy(update={"tiers": tiers})
    await _write(module, principal, "streak", clean.model_dump(mode="json"), "play streak")
    return parse_streak(module.config.streak)


@router.get("/admin/gamification/pace", response_model=PaceConfig)
async def get_pace(_: Manager, module: Module) -> PaceConfig:
    return parse_pace(module.config.pace)


@router.put("/admin/gamification/pace", response_model=PaceConfig)
async def put_pace(principal: Manager, body: PaceConfig, module: Module) -> PaceConfig:
    clean = body.model_copy(update={"factor": round(body.factor, 3), "values": sorted(set(body.values))})
    await _write(module, principal, "pace", clean.model_dump(mode="json"), "overall pace")
    return parse_pace(module.config.pace)


class LevelRewardsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rewards: list[LevelReward] = Field(max_length=100)


class LevelStepOut(BaseModel):
    level: int
    xp: int


class LevelRewardsOut(BaseModel):
    rewards: list[LevelReward]
    levels: list[LevelStepOut]


async def _rewards_out(module: Any) -> LevelRewardsOut:
    rewards = parse_rewards(module.config.level_rewards)
    curve = await module.levels.curve()
    top = max([30, *(r.level for r in rewards)])
    return LevelRewardsOut(
        rewards=rewards, levels=[LevelStepOut(level=n, xp=curve.threshold(n)) for n in range(1, top + 1)]
    )


@router.get("/admin/gamification/level-rewards", response_model=LevelRewardsOut)
async def get_level_rewards(_: Manager, module: Module) -> LevelRewardsOut:
    return await _rewards_out(module)


@router.put("/admin/gamification/level-rewards", response_model=LevelRewardsOut)
async def put_level_rewards(principal: Manager, body: LevelRewardsIn, module: Module) -> LevelRewardsOut:
    rewards = sorted({r.level: r for r in body.rewards}.values(), key=lambda r: r.level)
    value = [r.model_dump(mode="json") for r in rewards]
    await _write(module, principal, "level_rewards", value, "level rewards")
    return await _rewards_out(module)


class DayOut(BaseModel):
    day: str
    amount: int
    members: int


class MemberPointOut(BaseModel):
    day: str
    total: int


class MemberSeriesOut(BaseModel):
    user_id: UUID
    name: str | None
    gained: int
    points: list[MemberPointOut]


class SourceOut(BaseModel):
    source: str
    amount: int


class ProgressOut(BaseModel):
    value: str
    days: list[DayOut]
    members: list[MemberSeriesOut]
    sources: list[SourceOut]


@router.get("/admin/gamification/progress", response_model=ProgressOut)
async def progress(
    _: Manager,
    module: Module,
    value: Literal["xp", "coins", "contribution"] = "xp",
    days: Annotated[int, Query(ge=7, le=365)] = 30,
    top: Annotated[int, Query(ge=1, le=10)] = 5,
) -> ProgressOut:
    """Daily gains over the period (positive movements only), the members who gained most — with their
    running total day by day — and the share of each source (rules by key, achievements, manual…)."""
    zone = module.config.timezone or "UTC"
    since = utc_now(module.clock) - timedelta(days=days)
    day = cast(func.timezone(zone, LedgerTransaction.occurred_at), Date)
    gained = (
        LedgerTransaction.value == value,
        LedgerTransaction.delta > 0,
        LedgerTransaction.kind.in_(("grant", "manual", "refund", "correction")),
    )
    active = func.count(distinct(LedgerTransaction.user_id))
    async with module.database.session() as session:
        daily = (
            await session.execute(
                select(day, func.sum(LedgerTransaction.delta), active)
                .where(*gained, LedgerTransaction.occurred_at >= since)
                .group_by(day)
                .order_by(day)
            )
        ).all()
        leaders = (
            await session.execute(
                select(LedgerTransaction.user_id, func.sum(LedgerTransaction.delta).label("gained"))
                .where(*gained, LedgerTransaction.occurred_at >= since)
                .group_by(LedgerTransaction.user_id)
                .order_by(func.sum(LedgerTransaction.delta).desc())
                .limit(top)
            )
        ).all()
        ids = [row[0] for row in leaders]
        before: dict[UUID, int] = {
            user: int(amount or 0)
            for user, amount in (
                await session.execute(
                    select(LedgerTransaction.user_id, func.sum(LedgerTransaction.delta))
                    .where(
                        LedgerTransaction.user_id.in_(ids),
                        LedgerTransaction.value == value,
                        LedgerTransaction.occurred_at < since,
                    )
                    .group_by(LedgerTransaction.user_id)
                )
            ).all()
        }
        moves = (
            await session.execute(
                select(LedgerTransaction.user_id, day, func.sum(LedgerTransaction.delta))
                .where(
                    LedgerTransaction.user_id.in_(ids),
                    LedgerTransaction.value == value,
                    LedgerTransaction.occurred_at >= since,
                )
                .group_by(LedgerTransaction.user_id, day)
                .order_by(day)
            )
        ).all()
        source = func.coalesce(LedgerTransaction.rule_key, LedgerTransaction.source_kind)
        sources = (
            await session.execute(
                select(source, func.sum(LedgerTransaction.delta))
                .where(*gained, LedgerTransaction.occurred_at >= since)
                .group_by(source)
                .order_by(func.sum(LedgerTransaction.delta).desc())
                .limit(12)
            )
        ).all()
    directory = module.capabilities.system_providers(DIRECTORY)
    members: list[MemberSeriesOut] = []
    for user_id, total in leaders:
        name = None
        if directory:
            try:
                summary = await directory[0].provider.get_user_summary(user_id)
                name = summary.display_name if summary else None
            except Exception:
                name = None
        running = int(before.get(user_id) or 0)
        points: list[MemberPointOut] = []
        for owner, when, delta in moves:
            if owner != user_id:
                continue
            running += int(delta or 0)
            points.append(MemberPointOut(day=when.isoformat(), total=running))
        members.append(MemberSeriesOut(user_id=user_id, name=name, gained=int(total), points=points))
    return ProgressOut(
        value=value,
        days=[DayOut(day=d.isoformat(), amount=int(a or 0), members=int(m)) for d, a, m in daily],
        members=members,
        sources=[SourceOut(source=str(s), amount=int(a or 0)) for s, a in sources],
    )


class StreakNextOut(BaseModel):
    days: int
    multiplier: float


class MyStreakOut(BaseModel):
    enabled: bool
    days: int
    multiplier: float
    next: StreakNextOut | None


@router.get("/me/streak", response_model=MyStreakOut)
async def my_streak(principal: Me, module: Module) -> MyStreakOut:
    """The member's play streak today (or yesterday's, still alive) and the next tier."""
    state = await module.streaks.current(_me(principal), utc_now(module.clock))
    return MyStreakOut.model_validate(state)


class MemberPositionOut(BaseModel):
    user_id: UUID
    name: str | None
    days: int  # since the member's first XP
    xp: int
    level: int


class PopulationOut(BaseModel):
    members: list[MemberPositionOut]
    rate_median: float  # XP per day of the members active over the last 30 days
    rate_high: float  # the 80th percentile — the most active members
    active: int


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


@router.get("/admin/gamification/population", response_model=PopulationOut)
async def population(
    _: Manager, module: Module, limit: Annotated[int, Query(ge=10, le=1000)] = 300
) -> PopulationOut:
    """027: where members stand (days since their first XP, XP, level) and the pace of active members
    (XP per day over the last 30 days) — what the progression chart draws and projects."""
    now = utc_now(module.clock)
    window = now - timedelta(days=30)
    async with module.database.session() as session:
        rows = (
            await session.execute(
                select(
                    LedgerTransaction.user_id,
                    func.min(LedgerTransaction.occurred_at),
                    func.sum(LedgerTransaction.delta),
                    # the pace counts what members earn by themselves, not manual grants
                    func.sum(LedgerTransaction.delta).filter(
                        LedgerTransaction.occurred_at >= window,
                        LedgerTransaction.kind != "manual",
                        LedgerTransaction.delta > 0,
                    ),
                )
                .where(LedgerTransaction.value == "xp")
                .group_by(LedgerTransaction.user_id)
                .having(func.sum(LedgerTransaction.delta) > 0)
                .order_by(func.sum(LedgerTransaction.delta).desc())
                .limit(limit)
            )
        ).all()
        curve = await module.levels.curve(session)
    directory = module.capabilities.system_providers(DIRECTORY)
    members: list[MemberPositionOut] = []
    rates: list[float] = []
    for user_id, first, total, recent in rows:
        days = max(0, (now - first).days)
        if recent and int(recent) > 0:
            rates.append(int(recent) / min(30, max(1, days)))
        name = None
        if directory and len(members) < 50:
            try:
                summary = await directory[0].provider.get_user_summary(user_id)
                name = summary.display_name if summary else None
            except Exception:
                name = None
        members.append(
            MemberPositionOut(
                user_id=user_id, name=name, days=days, xp=int(total), level=curve.level_for(int(total))
            )
        )
    return PopulationOut(
        members=members,
        rate_median=round(_quantile(rates, 0.5), 2),
        rate_high=round(_quantile(rates, 0.8), 2),
        active=len(rates),
    )


class SourceDayOut(BaseModel):
    day: str
    amounts: dict[str, int]


class MySourcesOut(BaseModel):
    value: str
    total: int
    sources: list[SourceOut]
    days: list[SourceDayOut]


@router.get("/me/progression/sources", response_model=MySourcesOut)
async def my_sources(
    principal: Me,
    module: Module,
    value: Literal["xp", "coins", "contribution"] = "xp",
    days: Annotated[int, Query(ge=7, le=365)] = 30,
) -> MySourcesOut:
    """027: where my gains came from — actions by kind, quests, achievements, levels and the bonuses
    (streaks, campaigns, pace) on top — per day and in all."""
    result = await gain_sources(
        module.database,
        _me(principal),
        value,
        since_days(utc_now(module.clock), days),
        module.config.timezone or "UTC",
    )
    return MySourcesOut.model_validate(result)
