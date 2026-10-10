"""Demo progression history (#62): each demo member's last weeks, day after day — sign-ins, plays, requests
and daily objectives at their own pace — so the progression page, the gain sources, the leaderboards and
the levels look like those of a living portal. Demo data only, idempotent (one key per member, day and
kind).

* The XP of the former lump grants (and of test grants) is taken back by corrections dated with them: the
  history explains each level instead.
* Play days are streak days (the last ones in a row for the most active member).
* Demo members share their progression with the community, unless they chose otherwise.
* Achievements follow: those on a level or an amount of XP are unlocked when reached (dated with the
  moment the threshold was crossed) and withdrawn when not; the others are dated within the history.
"""

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from portalab.core.time import utc_now
from portalab.modules.gamification.ledger.writer import Entry
from portalab.modules.gamification.models import (
    Balance,
    LedgerTransaction,
    ProgressionPreference,
    StreakDay,
    UserAchievement,
)


@dataclass(frozen=True)
class Pace:
    days: int  # how far back the member's history goes
    active: float  # chance to come on a given day
    plays: tuple[int, int]  # plays on an active day
    requests: float  # chance to ask for a title
    daily: float  # chance to complete the daily objectives
    streak: int = 0  # the last days, every one active (a streak running)


PACES: dict[str, Pace] = {
    "alice": Pace(days=42, active=0.85, plays=(1, 4), requests=0.25, daily=0.7, streak=6),
    "admin": Pace(days=42, active=0.7, plays=(1, 3), requests=0.3, daily=0.5, streak=2),
    "bruno": Pace(days=30, active=0.6, plays=(1, 4), requests=0.2, daily=0.45),
    "chloe": Pace(days=16, active=0.55, plays=(0, 3), requests=0.15, daily=0.35),
}
SIGN_IN_XP, PLAY_XP, PLAY_COINS, REQUEST_XP, DAILY_XP, DAILY_COINS = 5, 15, 2, 10, 30, 10


async def seed_history(gamification: Any, people: dict[str, UUID]) -> str:
    now = utc_now()
    today = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    taken = granted = 0
    for name, pace in PACES.items():
        user = people.get(name)
        if user is None:
            continue
        taken += await _take_back_lumps(gamification, user)
        granted += await _history(gamification, name, user, pace, today)
    achievements = await _achievements(gamification, people, today)
    await _share_progression(gamification, [people[n] for n in PACES if n in people], now)
    return f"{granted} history grants, {taken} lump corrections, {achievements} achievements dated"


async def _take_back_lumps(gamification: Any, user: UUID) -> int:
    """Manual XP grants (demo lumps, test grants) reversed by corrections dated with them."""
    done = 0
    async with gamification.database.unit_of_work() as uow:
        grants = (
            await uow.session.execute(
                select(LedgerTransaction).where(
                    LedgerTransaction.user_id == user,
                    LedgerTransaction.value == "xp",
                    LedgerTransaction.kind == "manual",
                    LedgerTransaction.delta > 0,
                )
            )
        ).scalars()
        for grant in list(grants):
            reversed_ = -int(
                await uow.session.scalar(
                    select(func.coalesce(func.sum(LedgerTransaction.delta), 0)).where(
                        LedgerTransaction.reverses_transaction_id == grant.id
                    )
                )
                or 0
            )
            balance = await uow.session.get(Balance, (user, "xp"))
            take = min(grant.delta - reversed_, balance.amount if balance else 0)
            if take <= 0:
                continue
            recorded = await gamification.writer.record(
                uow.session,
                Entry(
                    user_id=user,
                    value="xp",
                    delta=-take,
                    kind="correction",
                    source_kind="manual",
                    idempotency_key=f"demo-history:takeback:{grant.id}",
                    occurred_at=grant.occurred_at,
                    reason="Demo data: the progression history explains the level instead",
                    reverses_transaction_id=grant.id,
                ),
            )
            done += not recorded.duplicate
    return done


async def _history(gamification: Any, name: str, user: UUID, pace: Pace, today: datetime) -> int:
    rng = random.Random(f"demo-history:{name}")  # noqa: S311 — demo data
    entries: list[Entry] = []
    play_days = []
    for back in range(pace.days, 0, -1):
        day = today - timedelta(days=back)
        active = back <= pace.streak or rng.random() < pace.active
        plays = rng.randint(*pace.plays)
        request = rng.random() < pace.requests
        daily = rng.random() < pace.daily
        hour = rng.randint(8, 22)
        if not active:
            continue
        at = day + timedelta(hours=hour, minutes=rng.randint(0, 50))
        key = f"demo-history:{name}:{day.date().isoformat()}"
        entries.append(_grant(user, "xp", SIGN_IN_XP, "reward_rule", f"{key}:signin", at, "sign_in_bonus"))
        for n in range(plays):
            when = at + timedelta(minutes=20 + 50 * n)
            entries.append(
                _grant(user, "xp", PLAY_XP, "reward_rule", f"{key}:play{n}", when, "media_playback")
            )
            entries.append(
                _grant(user, "coins", PLAY_COINS, "reward_rule", f"{key}:playc{n}", when, "media_playback")
            )
        if plays:
            play_days.append(day.date())
        if request:
            entries.append(
                _grant(user, "xp", REQUEST_XP, "reward_rule", f"{key}:request", at, "media_request")
            )
        if daily:
            done = at + timedelta(hours=1)
            entries.append(_grant(user, "xp", DAILY_XP, "daily", f"{key}:daily", done))
            entries.append(_grant(user, "coins", DAILY_COINS, "daily", f"{key}:dailyc", done))
    recorded = 0
    async with gamification.database.unit_of_work() as uow:
        for entry in sorted(entries, key=lambda e: e.occurred_at):
            result = await gamification.writer.record(uow.session, entry)
            recorded += not result.duplicate
        if play_days:
            await uow.session.execute(
                insert(StreakDay)
                .values([{"user_id": user, "day": d} for d in play_days])
                .on_conflict_do_nothing()
            )
    return recorded


async def _share_progression(gamification: Any, users: list[UUID], now: datetime) -> None:
    """Demo members share their progression with the community (leaderboards, profiles) — unless they
    already chose otherwise."""
    async with gamification.database.unit_of_work() as uow:
        await uow.session.execute(
            insert(ProgressionPreference)
            .values([{"user_id": u, "level": "community", "updated_at": now} for u in users])
            .on_conflict_do_nothing()
        )


def _grant(
    user: UUID, value: str, amount: int, source: str, key: str, at: datetime, rule: str | None = None
) -> Entry:
    return Entry(
        user_id=user,
        value=value,
        delta=amount,
        kind="grant",
        source_kind=source,
        idempotency_key=key,
        occurred_at=at,
        rule_key=rule,
        base_amount=amount,
    )


async def _crossings(
    gamification: Any, user: UUID, curve: Any
) -> tuple[dict[int, datetime], list[tuple[int, datetime]]]:
    """When each level was reached and the XP total after each instant (the ledger replayed)."""
    async with gamification.database.session() as session:
        moves = (
            await session.execute(
                select(LedgerTransaction.occurred_at, func.sum(LedgerTransaction.delta))
                .where(LedgerTransaction.user_id == user, LedgerTransaction.value == "xp")
                .group_by(LedgerTransaction.occurred_at)
                .order_by(LedgerTransaction.occurred_at)
            )
        ).all()
    xp, reached, levels, totals = 0, 1, {}, []
    for at, delta in moves:
        xp += int(delta)
        totals.append((xp, at))
        level = curve.level_for(max(0, xp))
        for n in range(reached + 1, level + 1):
            levels[n] = at
        reached = max(reached, level)
    return levels, totals


async def _achievements(gamification: Any, people: dict[str, UUID], today: datetime) -> int:
    now = utc_now()
    curve = await gamification.levels.curve()
    definitions = await gamification.achievements.definitions(now)
    changed = 0
    for name, pace in PACES.items():
        user = people.get(name)
        if user is None:
            continue
        levels, totals = await _crossings(gamification, user, curve)
        level = curve.level_for(max(0, totals[-1][0] if totals else 0))
        xp = totals[-1][0] if totals else 0
        rng = random.Random(f"demo-history:achievements:{name}")  # noqa: S311
        start = today - timedelta(days=pace.days)
        async with gamification.database.session() as session:
            unlocked = {
                row.achievement_key: row
                for row in (
                    await session.execute(select(UserAchievement).where(UserAchievement.user_id == user))
                ).scalars()
            }
        for definition in definitions:
            criteria = definition.definition.criteria
            when: datetime | None = None
            threshold = False
            met = True
            for criterion in criteria:
                if criterion.kind == "level_at_least":
                    threshold = True
                    met = met and level >= criterion.level
                    when = levels.get(criterion.level, when)
                elif criterion.kind == "value_at_least" and criterion.value == "xp":
                    threshold = True
                    met = met and xp >= criterion.amount
                    when = next((at for total, at in totals if total >= criterion.amount), when)
            row = unlocked.get(definition.key)
            if threshold and not met and row is not None:
                async with gamification.database.unit_of_work() as uow:  # reached by a test grant only
                    await uow.session.execute(delete(UserAchievement).where(UserAchievement.id == row.id))
                changed += 1
                continue
            if threshold and met and row is None:
                async with gamification.database.unit_of_work() as uow:
                    await gamification.achievements.unlock_by_key(uow.session, user, definition.key, now)
                changed += 1
            elif row is None or row.unlocked_at < today - timedelta(days=7):
                continue  # not unlocked, or already dated within the history
            if when is None:  # any other achievement: a day of the history
                when = start + timedelta(days=rng.randint(1, pace.days - 1), hours=rng.randint(9, 22))
            async with gamification.database.unit_of_work() as uow:
                await uow.session.execute(
                    update(UserAchievement)
                    .where(UserAchievement.user_id == user, UserAchievement.achievement_key == definition.key)
                    .values(unlocked_at=when)
                )
            changed += 1
    return changed
