"""Level-up moment (027): what the member sees when a level is reached — the new level and its rank, the
level rewards of every tier crossed (Coins, Contribution, an offered product), the achievements just
unlocked with what they gave, and the XP to the next level. Read-only, own data only."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.models import Balance, UserAchievement
from portalab.modules.gamification.streaks.level_rewards import parse_rewards

RECENT = timedelta(minutes=10)  # achievements unlocked around the level-up


async def level_up_summary(
    database: Database,
    levels: Any,
    achievements: Any,
    config: Any,
    user: UUID,
    level: int,
    since_level: int | None = None,
    *,
    clock: Clock | None = None,
) -> dict[str, Any]:
    now: datetime = utc_now(clock)
    previous = max(1, min(level - 1, since_level if since_level is not None else level - 1))
    tiers = [
        {
            "level": tier.level,
            "coins": tier.coins,
            "contribution": tier.contribution,
            "product": tier.product,
            "label": tier.label,
        }
        for tier in parse_rewards(config.level_rewards)
        if previous < tier.level <= level
    ]
    async with database.session() as session:
        curve = await levels.curve(session)
        balance = await session.get(Balance, (user, "xp"))
        recent = (
            (
                await session.execute(
                    select(UserAchievement).where(
                        UserAchievement.user_id == user, UserAchievement.unlocked_at >= now - RECENT
                    )
                )
            )
            .scalars()
            .all()
        )
    xp = int(balance.amount) if balance else 0
    definitions = {d.key: d.definition for d in await achievements.definitions(now)}
    unlocked = []
    for row in sorted(recent, key=lambda r: r.unlocked_at):
        definition = definitions.get(row.achievement_key)
        if definition is None:
            continue
        unlocked.append(
            {
                "key": row.achievement_key,
                "label": definition.label,
                "description": definition.description,
                "icon": definition.icon,
                "rewards": [{"value": r.value, "amount": r.amount} for r in definition.rewards],
                "unlocks": [u.model_dump() for u in definition.unlocks],
            }
        )
    return {
        "level": level,
        "previous": previous,
        "xp": xp,
        "level_floor": curve.threshold(level),
        "next_level_at": curve.next_threshold(xp),
        "rewards": tiers,
        "achievements": unlocked,
    }
