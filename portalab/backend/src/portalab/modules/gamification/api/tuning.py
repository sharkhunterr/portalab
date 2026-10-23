"""Gamification tuning (027): what the administration pages need besides raw rules — the actions that can
be rewarded (event types and their rewardable attributes), play streaks, level rewards and how members
progress over time (daily gains, the members who progress most, where the gains come from)."""

import types
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal, Union, get_args, get_origin
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Date, cast, distinct, func, literal, select, tuple_
from sqlalchemy.orm import aliased

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.media_core import CATALOG as MEDIA_CATALOG
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.core.time import utc_now
from portalab.modules.gamification.api.me import Me, Module, _me
from portalab.modules.gamification.events import OWN_TYPES
from portalab.modules.gamification.models import (
    Achievement,
    GainContext,
    LedgerTransaction,
    PlayKind,
    Quest,
    RewardRule,
)
from portalab.modules.gamification.permissions import MANAGE
from portalab.modules.gamification.progression.plays import plays as plays_by_kind
from portalab.modules.gamification.progression.sources import (
    PLAY_SOURCES,
    QUESTS,
    action_of,
    is_wheel,
    play_source,
    since_days,
    split,
)
from portalab.modules.gamification.progression.sources import sources as gain_sources
from portalab.modules.gamification.progression.timeline import timeline as gain_timeline
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
    value: Literal["xp", "coins", "contribution", "booster"] = "xp",
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
    freezes: int = 0  # #54: freezes owned, each covering one missed day
    last_frozen: date | None = None


@router.get("/me/streak", response_model=MyStreakOut)
async def my_streak(principal: Me, module: Module) -> MyStreakOut:
    """The member's play streak today (or yesterday's, still alive) and the next tier."""
    state = await module.streaks.current(_me(principal), utc_now(module.clock))
    perks = await module.perks.state(_me(principal))
    return MyStreakOut.model_validate(
        {**state, "freezes": perks["freezes"], "last_frozen": perks["last_frozen"]}
    )


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
    value: Literal["xp", "coins", "contribution", "booster"] = "xp",
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


class PlayKindOut(BaseModel):
    play: str  # episode, movie, live, book, audiobook, music, game — or media (an unknown kind)
    sittings: int  # plays finished or interrupted
    finished: int  # works watched (listened to, read) to the end
    watched_s: int  # time watched, listened to or read
    xp: int  # XP earned by these plays, bonuses included
    coins: int
    members: int  # how many members played this kind


class PlaysDayOut(BaseModel):
    day: str
    sittings: dict[str, int]


class PlaysOut(BaseModel):
    kinds: list[PlayKindOut]
    days: list[PlaysDayOut]


@router.get("/me/progression/plays", response_model=PlaysOut)
async def my_plays(principal: Me, module: Module, days: Annotated[int, Query(ge=7, le=365)] = 30) -> PlaysOut:
    """Issue 160: my plays by kind over the period — sittings, works finished, time, XP and Coins."""
    since = since_days(utc_now(module.clock), days)
    result = await plays_by_kind(module.database, _me(principal), since, module.config.timezone or "UTC")
    return PlaysOut.model_validate(result)


@router.get("/admin/gamification/plays", response_model=PlaysOut)
async def all_plays(
    _: Manager,
    module: Module,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
    member: UUID | None = None,
) -> PlaysOut:
    """Issue 160: every member's plays by kind (or one member's) — sittings, works finished, time, the XP and
    Coins they earned and how many members played each kind."""
    since = since_days(utc_now(module.clock), days)
    result = await plays_by_kind(module.database, member, since, module.config.timezone or "UTC")
    return PlaysOut.model_validate(result)


class MemberProgressOut(BaseModel):
    user_id: UUID
    name: str | None
    balance: int  # what the member holds now
    gained: int  # gained over the period
    sources: list[SourceOut]  # the period's gains by kind (plays, quests, achievements, bonuses…)
    days: list[SourceDayOut]  # and day by day
    points: list[MemberPointOut]  # the running balance, day by day


class MembersProgressOut(BaseModel):
    value: str
    members: list[MemberProgressOut]


MEMBERS_SHOWN = 50


@router.get("/admin/gamification/members", response_model=MembersProgressOut)
async def members_progress(
    _: Manager,
    module: Module,
    value: Literal["xp", "coins", "contribution", "booster"] = "xp",
    days: Annotated[int, Query(ge=7, le=365)] = 30,
    member: UUID | None = None,
) -> MembersProgressOut:
    """#104: every member's progression over the period (or one member's) — their gains by kind, day by day,
    and their running balance — to compare them, or follow one; the most advanced first."""
    zone = module.config.timezone or "UTC"
    since = since_days(utc_now(module.clock), days)
    day = cast(func.timezone(zone, LedgerTransaction.occurred_at), Date)
    of_value = LedgerTransaction.value == value
    async with module.database.session() as session:
        query = select(LedgerTransaction.user_id, func.sum(LedgerTransaction.delta)).where(of_value)
        if member is not None:
            query = query.where(LedgerTransaction.user_id == member)
        balances = (
            await session.execute(
                query.group_by(LedgerTransaction.user_id)
                .order_by(func.sum(LedgerTransaction.delta).desc())
                .limit(MEMBERS_SHOWN)
            )
        ).all()
        ids = [user for user, _ in balances]
        theirs = (of_value, LedgerTransaction.user_id.in_(ids))
        before: dict[UUID, int] = {
            user: int(amount or 0)
            for user, amount in (
                await session.execute(
                    select(LedgerTransaction.user_id, func.sum(LedgerTransaction.delta))
                    .where(*theirs, LedgerTransaction.occurred_at < since)
                    .group_by(LedgerTransaction.user_id)
                )
            ).all()
        }
        moves = (
            await session.execute(
                select(LedgerTransaction.user_id, day, func.sum(LedgerTransaction.delta))
                .where(*theirs, LedgerTransaction.occurred_at >= since)
                .group_by(LedgerTransaction.user_id, day)
                .order_by(day)
            )
        ).all()
    directory = module.capabilities.system_providers(DIRECTORY)
    members: list[MemberProgressOut] = []
    for user_id, balance in balances:
        name = None
        if directory:
            try:
                summary = await directory[0].provider.get_user_summary(user_id)
                name = summary.display_name if summary else None
            except Exception:
                name = None
        gains = await gain_sources(module.database, user_id, value, since, zone)
        running = int(before.get(user_id) or 0)
        points = [MemberPointOut(day=since.astimezone(UTC).date().isoformat(), total=running)]
        for owner, when, delta in moves:
            if owner == user_id:
                running += int(delta or 0)
                points.append(MemberPointOut(day=when.isoformat(), total=running))
        members.append(
            MemberProgressOut(
                user_id=user_id,
                name=name,
                balance=int(balance or 0),
                gained=int(gains["total"]),
                sources=[SourceOut.model_validate(x) for x in gains["sources"]],
                days=[SourceDayOut.model_validate(x) for x in gains["days"]],
                points=points,
            )
        )
    return MembersProgressOut(value=value, members=members)


class TimelineDayOut(BaseModel):
    day: str
    xp: int
    coins: int
    contribution: int


class LevelUpOut(BaseModel):
    level: int
    at: str
    day: str


class MyTimelineOut(BaseModel):
    days: list[TimelineDayOut]
    start_level: int
    level_ups: list[LevelUpOut]


@router.get("/me/progression/timeline", response_model=MyTimelineOut)
async def my_timeline(
    principal: Me,
    module: Module,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
) -> MyTimelineOut:
    """#62: my XP, Coins and Contribution gained day by day, and the moments I reached a level."""
    result = await gain_timeline(
        module.database,
        _me(principal),
        since_days(utc_now(module.clock), days),
        module.config.timezone or "UTC",
        await module.levels.curve(),
    )
    return MyTimelineOut.model_validate(result)


class ValueDetailOut(BaseModel):
    balance: int  # held now
    gained: int  # over the period
    spent: int  # spent over the period (the shop), as a positive number — a withdrawal corrects the gains


class DetailDayOut(BaseModel):
    day: str
    xp: int
    coins: int
    contribution: int
    spent_coins: int
    levels: list[int]  # the levels reached that day


class MemberDetailOut(BaseModel):
    user_id: UUID
    name: str | None
    level: int
    start_level: int  # at the start of the period
    xp: ValueDetailOut
    coins: ValueDetailOut
    contribution: ValueDetailOut
    level_ups: list[LevelUpOut]
    days: list[DetailDayOut]


class MembersDetailOut(BaseModel):
    members: list[MemberDetailOut]


@router.get("/admin/gamification/members/details", response_model=MembersDetailOut)
async def members_details(
    _: Manager,
    module: Module,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
    member: UUID | None = None,
) -> MembersDetailOut:
    """#106: each member's detail over the period — XP, Coins and Contribution held, gained and spent, the
    levels reached and when — in all and day by day; the most advanced first (or one member)."""
    zone = module.config.timezone or "UTC"
    since = since_days(utc_now(module.clock), days)
    day = cast(func.timezone(zone, LedgerTransaction.occurred_at), Date)
    curve = await module.levels.curve()
    async with module.database.session() as session:
        query = select(LedgerTransaction.user_id, LedgerTransaction.value, func.sum(LedgerTransaction.delta))
        if member is not None:
            query = query.where(LedgerTransaction.user_id == member)
        totals = (
            await session.execute(query.group_by(LedgerTransaction.user_id, LedgerTransaction.value))
        ).all()
        balances: dict[UUID, dict[str, int]] = {}
        for user, value, amount in totals:
            balances.setdefault(user, {})[value] = int(amount or 0)
        ids = sorted(balances, key=lambda u: -balances[u].get("xp", 0))[:MEMBERS_SHOWN]
        taken = (
            await session.execute(
                select(
                    LedgerTransaction.user_id, LedgerTransaction.value, day, func.sum(LedgerTransaction.delta)
                )
                .where(
                    LedgerTransaction.user_id.in_(ids),
                    LedgerTransaction.delta < 0,
                    LedgerTransaction.kind != "correction",  # a correction lowers the gain itself
                    LedgerTransaction.occurred_at >= since,
                )
                .group_by(LedgerTransaction.user_id, LedgerTransaction.value, day)
            )
        ).all()
    spent: dict[UUID, dict[str, dict[str, int]]] = {}
    for user, value, when, amount in taken:
        spent.setdefault(user, {}).setdefault(value, {})[when.isoformat()] = -int(amount or 0)
    directory = module.capabilities.system_providers(DIRECTORY)
    out: list[MemberDetailOut] = []
    for user_id in ids:
        name = None
        if directory:
            try:
                summary = await directory[0].provider.get_user_summary(user_id)
                name = summary.display_name if summary else None
            except Exception:
                name = None
        line = await gain_timeline(module.database, user_id, since, zone, curve)
        mine = spent.get(user_id, {})
        reached: dict[str, list[int]] = {}
        for up in line["level_ups"]:
            reached.setdefault(up["day"], []).append(up["level"])
        gained = {v: sum(d[v] for d in line["days"]) for v in ("xp", "coins", "contribution")}
        dates = sorted(
            {d["day"] for d in line["days"]} | {d for v in mine.values() for d in v} | set(reached)
        )
        by_day = {d["day"]: d for d in line["days"]}
        held = balances.get(user_id, {})

        values = {
            v: ValueDetailOut(balance=held.get(v, 0), gained=gained[v], spent=sum(mine.get(v, {}).values()))
            for v in ("xp", "coins", "contribution")
        }

        out.append(
            MemberDetailOut(
                user_id=user_id,
                name=name,
                level=curve.level_for(max(0, held.get("xp", 0))),
                start_level=int(line["start_level"]),
                xp=values["xp"],
                coins=values["coins"],
                contribution=values["contribution"],
                level_ups=[LevelUpOut.model_validate(up) for up in line["level_ups"]],
                days=[
                    DetailDayOut(
                        day=d,
                        xp=by_day.get(d, {}).get("xp", 0),
                        coins=by_day.get(d, {}).get("coins", 0),
                        contribution=by_day.get(d, {}).get("contribution", 0),
                        spent_coins=mine.get("coins", {}).get(d, 0),
                        levels=reached.get(d, []),
                    )
                    for d in dates
                ],
            )
        )
    return MembersDetailOut(members=out)


class BonusOut(BaseModel):
    source: str  # streak, campaigns, pace, boost
    amount: float  # its share of the operation's amount


class OperationOut(BaseModel):
    id: UUID
    occurred_at: datetime
    user_id: UUID
    name: str | None
    value: str
    delta: int
    kind: str  # grant, spend, correction, manual…
    source_kind: str  # reward_rule, quest, achievement, marketplace, manual…
    source: str  # what made it, as on the progression charts: media, quests, achievements, shop, levels…
    label: str | None  # the rule's, achievement's or quest's name
    reason: str | None  # an administrator's justification
    balance: int  # the member's balance of this value right after
    level: int | None  # for XP: the level right after
    level_up: bool  # for XP: a new level was reached
    play: str | None = None  # issue 160: for a play, what was played (episode, movie, book, audiobook…)
    title: str | None = None  # and its title, when the catalog still knows it
    # the other member involved (e.g. who watched a title this member asked for) — the administration's only
    other: str | None = None
    # the bonuses on top of the action's own amount (streak, campaign, pace, boost), as on the charts
    bonuses: list[BonusOut] = Field(default_factory=list)


class OperationsOut(BaseModel):
    items: list[OperationOut]
    next_cursor: str | None
    total: int  # operations matching the filters over the period


OPERATIONS_PAGE = 100


def _source(
    kind: str,
    source_kind: str,
    delta: int,
    event_type: str | None,
    played: str | None = None,
    source_ref: str | None = None,
) -> str:
    if is_wheel(source_kind, source_ref):
        return "wheel"  # issue 225: the daily wheel, won or lost
    if source_kind == "reward_rule":
        return action_of(event_type, played)
    if source_kind in QUESTS:
        return "quests"
    if source_kind == "achievement":
        return "achievements"
    if source_kind == "level_reward":
        return "levels"
    if source_kind == "marketplace" or (delta < 0 and kind in ("spend", "reserve_consume")):
        return "shop"
    if source_kind == "manual":
        return "admin"  # given, taken back or corrected by an administrator
    return "other"


async def _labels(session: Any) -> dict[tuple[str, str], str]:
    """The latest name of every rule, achievement and quest."""
    out: dict[tuple[str, str], str] = {}
    for kind, model in (("rule", RewardRule), ("achievement", Achievement), ("quest", Quest)):
        rows = (await session.execute(select(model.key, model.definition).order_by(model.version))).all()
        for key, definition in rows:
            label = (definition or {}).get("label")
            if label:
                out[(kind, key)] = str(label)
    return out


def _label_of(labels: dict[tuple[str, str], str], source_ref: str | None, rule_key: str | None) -> str | None:
    if rule_key:
        return labels.get(("rule", rule_key), rule_key)
    head, _, rest = (source_ref or "").partition(":")
    if head in ("achievement", "quest"):
        key = rest.split(":", 1)[0]
        return labels.get((head, key), key)
    if head == "level":
        return rest or None
    return None


@router.get("/admin/gamification/operations", response_model=OperationsOut)
async def operations(
    principal: Manager,
    module: Module,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
    member: UUID | None = None,
    value: Literal["xp", "coins", "contribution", "booster"] | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=5, le=OPERATIONS_PAGE)] = OPERATIONS_PAGE,
    play: Annotated[str | None, Query(max_length=24)] = None,
) -> OperationsOut:
    """#107: every operation of every member (or one member) over the period, the latest first (by the time
    it happened: a play rewarded late from a history sits on its day) — what was gained or spent, what made
    it, the balance after it in that order and, for XP, the level reached."""
    return await _operations(module, principal, days, member, value, cursor, limit, play, team=True)


@router.get("/me/progression/operations", response_model=OperationsOut)
async def my_operations(
    principal: Me,
    module: Module,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
    value: Literal["xp", "coins", "contribution", "booster"] | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=5, le=OPERATIONS_PAGE)] = OPERATIONS_PAGE,
    play: Annotated[str | None, Query(max_length=24)] = None,
) -> OperationsOut:
    """#114: my own journal — the same table as the administration's, mine only."""
    return await _operations(module, principal, days, _me(principal), value, cursor, limit, play)


async def _operations(
    module: Any,
    viewer: Principal,
    days: int,
    member: UUID | None,
    value: str | None,
    cursor: str | None,
    limit: int,
    play: str | None = None,
    *,
    team: bool = False,  # the administration's journal: the other member involved is named
) -> OperationsOut:
    since = since_days(utc_now(module.clock), days)
    curve = await module.levels.curve()
    running = (
        func.sum(LedgerTransaction.delta)
        .over(
            partition_by=(LedgerTransaction.user_id, LedgerTransaction.value),
            order_by=(LedgerTransaction.occurred_at, LedgerTransaction.seq),
        )
        .label("running")
    )
    inner = select(LedgerTransaction, running)
    if member is not None:
        inner = inner.where(LedgerTransaction.user_id == member)
    if value is not None:
        inner = inner.where(LedgerTransaction.value == value)
    ledger = inner.subquery()
    row = aliased(LedgerTransaction, ledger)
    query = select(row, ledger.c.running).where(row.occurred_at >= since)
    counted = select(func.count()).select_from(ledger).where(ledger.c.occurred_at >= since)
    if play:  # issue 160: only the gains of one kind of play (episodes, films, books…) — balances unchanged
        raw = [kind for kind, source in PLAY_SOURCES.items() if source == play] or [play]
        of_play = select(PlayKind.event_id).where(PlayKind.kind.in_(raw))
        query = query.where(row.trigger_event_id.in_(of_play))
        counted = counted.where(ledger.c.trigger_event_id.in_(of_play))
    after = _cursor(cursor)
    if after is not None:
        query = query.where(tuple_(row.occurred_at, row.seq) < tuple_(literal(after[0]), literal(after[1])))
    async with module.database.session() as session:
        rows = (
            await session.execute(query.order_by(row.occurred_at.desc(), row.seq.desc()).limit(limit + 1))
        ).all()
        total = int((await session.execute(counted)).scalar_one())
        labels = await _labels(session)
        events = {
            key: event_type
            for key, event_type in (
                await session.execute(select(RewardRule.key, RewardRule.event_type))
            ).all()
        }
        more = len(rows) > limit
        rows = rows[:limit]
        triggers = {t.trigger_event_id for t, _ in rows if t.trigger_event_id is not None}
        plays: dict[UUID, tuple[str, str | None]] = {
            event: (kind, played)
            for event, kind, played in (
                await session.execute(
                    select(PlayKind.event_id, PlayKind.kind, PlayKind.object).where(
                        PlayKind.event_id.in_(triggers)
                    )
                )
            ).all()
        }
        contexts: dict[UUID, tuple[str | None, UUID | None]] = {
            event: (about, other)
            for event, about, other in (
                await session.execute(
                    select(GainContext.event_id, GainContext.object, GainContext.other_user).where(
                        GainContext.event_id.in_(triggers)
                    )
                )
            ).all()
        }
    titles = await _titles(
        module, viewer, {o for _, o in plays.values() if o} | {o for o, _ in contexts.values() if o}
    )
    others = {other for _, other in contexts.values() if other} if team else set()
    names = await _names(module, {t.user_id for t, _ in rows} | others)
    items: list[OperationOut] = []
    for t, running_after in rows:
        after_it = int(running_after or 0)
        action = _source(
            t.kind,
            t.source_kind,
            int(t.delta),
            events.get(t.rule_key or ""),
            played[0] if (played := plays.get(t.trigger_event_id)) else None,
            t.source_ref,
        )
        shares = split(t.source_kind, int(t.delta), int(t.base_amount or 0), t.modifiers or {}, action)
        level = curve.level_for(max(0, after_it)) if t.value == "xp" else None
        before = curve.level_for(max(0, after_it - int(t.delta))) if t.value == "xp" else None
        items.append(
            OperationOut(
                id=t.id,
                occurred_at=t.occurred_at,
                user_id=t.user_id,
                name=names.get(t.user_id),
                value=t.value,
                delta=int(t.delta),
                kind=t.kind,
                source_kind=t.source_kind,
                source=action,
                label=_label_of(labels, t.source_ref, t.rule_key),
                reason=None if action == "wheel" else t.reason,  # the interface says what the wheel gave
                balance=after_it,
                level=level,
                level_up=level is not None and before is not None and level > before,
                play=play_source(played[0]) if played else None,
                title=(
                    titles.get(played[1] or "")
                    if played
                    else titles.get(about[0] or "")
                    if (about := contexts.get(t.trigger_event_id))
                    else None
                ),
                other=(
                    names.get(about[1])
                    if team and (about := contexts.get(t.trigger_event_id)) and about[1]
                    else None
                ),
                bonuses=[
                    BonusOut(source=source, amount=round(amount, 1))
                    for source, amount in shares.items()
                    if source != action and amount > 0
                ],
            )
        )
    last = rows[-1][0] if more and rows else None
    return OperationsOut(
        items=items,
        next_cursor=f"{last.occurred_at.isoformat()}|{last.seq}" if last else None,
        total=total,
    )


def _cursor(cursor: str | None) -> tuple[datetime, int] | None:
    """A page ends at an operation: its time and its sequence (two at the same time keep their order)."""
    when, _, seq = (cursor or "").rpartition("|")
    try:
        return datetime.fromisoformat(when), int(seq)
    except ValueError:
        return None


async def _titles(module: Any, viewer: Principal, objects: set[str]) -> dict[str, str]:
    """Issue 160: the titles of the plays shown, as the viewer may see them (the catalog decides)."""
    catalog = module.capabilities.system_providers(MEDIA_CATALOG)
    out: dict[str, str] = {}
    if not catalog:
        return out
    for raw in objects:
        try:
            summary = await catalog[0].provider.get(UUID(raw), viewer)
        except Exception:
            summary = None  # gone from the catalog, or hidden from this viewer: the kind alone shows
        if summary is not None:
            out[raw] = summary.title
    return out


async def _names(module: Any, ids: set[UUID]) -> dict[UUID, str | None]:
    directory = module.capabilities.system_providers(DIRECTORY)
    out: dict[UUID, str | None] = {}
    for user_id in ids:
        name = None
        if directory:
            try:
                summary = await directory[0].provider.get_user_summary(user_id)
                name = summary.display_name if summary else None
            except Exception:
                name = None
        out[user_id] = name
    return out
