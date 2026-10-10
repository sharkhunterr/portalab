"""My progression over time (#62, the progression page): what each value — XP, Coins, Contribution — grew by
day after day over a period, and the moments a level was reached (replayed from the XP ledger against the
level curve: the movement that crossed each threshold). Own data only."""

from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Date, cast, func, or_, select

from portalab.core.db import Database
from portalab.modules.gamification.levels.curve import Curve
from portalab.modules.gamification.models import LedgerTransaction
from portalab.modules.gamification.progression.sources import GAINS

VALUES = ("xp", "coins", "contribution")
MAX_LEVEL_UPS = 60


async def timeline(
    database: Database, user: UUID, since: datetime, zone: str, curve: Curve
) -> dict[str, Any]:
    day = cast(func.timezone(zone, LedgerTransaction.occurred_at), Date)
    async with database.session() as session:
        gains = (
            await session.execute(
                select(day, LedgerTransaction.value, func.sum(LedgerTransaction.delta))
                .where(
                    LedgerTransaction.user_id == user,
                    or_(LedgerTransaction.delta > 0, LedgerTransaction.kind == "correction"),
                    LedgerTransaction.kind.in_(GAINS),
                    LedgerTransaction.occurred_at >= since,
                )
                .group_by(day, LedgerTransaction.value)
            )
        ).all()
        before = (
            await session.execute(
                select(func.coalesce(func.sum(LedgerTransaction.delta), 0)).where(
                    LedgerTransaction.user_id == user,
                    LedgerTransaction.value == "xp",
                    LedgerTransaction.occurred_at < since,
                )
            )
        ).scalar_one()
        moves = (
            await session.execute(
                select(LedgerTransaction.occurred_at, day, LedgerTransaction.delta)
                .where(
                    LedgerTransaction.user_id == user,
                    LedgerTransaction.value == "xp",
                    LedgerTransaction.occurred_at >= since,
                )
                .order_by(LedgerTransaction.occurred_at, LedgerTransaction.seq)
            )
        ).all()
    per_day: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(VALUES, 0))
    for when, value, amount in gains:
        if value in VALUES:
            per_day[when.isoformat()][value] += int(amount or 0)
    xp = int(before or 0)
    reached = curve.level_for(max(0, xp))
    start_level = reached
    level_ups: list[dict[str, Any]] = []
    # movements of the same instant count as one (a correction dated with the grant it takes back)
    instants: list[tuple[datetime, Any, int]] = []
    for at, when, delta in moves:
        if instants and instants[-1][0] == at:
            instants[-1] = (at, when, instants[-1][2] + int(delta))
        else:
            instants.append((at, when, int(delta)))
    for at, when, delta in instants:
        xp += delta
        level = curve.level_for(max(0, xp))
        if level > reached:
            # one movement may jump several levels: each is a moment of its own, at the same time
            level_ups.extend(
                {"level": n, "at": at.isoformat(), "day": when.isoformat()}
                for n in range(reached + 1, level + 1)
            )
            reached = level
    return {
        "days": [
            {"day": d, **{v: max(0, n) for v, n in amounts.items()}} for d, amounts in sorted(per_day.items())
        ],
        "start_level": start_level,
        "level_ups": level_ups[-MAX_LEVEL_UPS:],
    }
