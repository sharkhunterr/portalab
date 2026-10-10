"""Progression (T010, T024, T028; FR-002): the three values shown **separately** with the derived level;
``ProgressionReader`` for 017/015/012."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.economy import Progress
from portalab.core.db import Database
from portalab.modules.gamification.achievements.evaluator import rarity_of
from portalab.modules.gamification.levels.service import LevelService
from portalab.modules.gamification.models import Achievement, Balance, Reservation, UserAchievement


class ProgressionService:
    def __init__(
        self,
        database: Database,
        levels: LevelService,
        shares: Callable[[], Awaitable[dict[str, float]]] | None = None,
    ) -> None:
        self.database = database
        self.levels = levels
        self.shares = shares  # #46: each achievement's unlock share, for its rarity on profiles

    async def progress(self, user: UUID) -> Progress:
        async with self.database.session() as session:
            amounts = {
                value: int(amount)
                for value, amount in (
                    await session.execute(
                        select(Balance.value, Balance.amount).where(Balance.user_id == user)
                    )
                ).all()
            }
            reserved = int(
                await session.scalar(
                    select(func.coalesce(func.sum(Reservation.amount), 0)).where(
                        Reservation.user_id == user, Reservation.status == "active"
                    )
                )
                or 0
            )
            achievements = int(
                await session.scalar(
                    select(func.count()).select_from(UserAchievement).where(UserAchievement.user_id == user)
                )
                or 0
            )
        curve = await self.levels.curve()
        xp = amounts.get("xp", 0)
        level = curve.level_for(xp)
        return Progress(
            user_id=user,
            xp=xp,
            level=level,
            level_floor=curve.threshold(level),
            next_level_at=curve.next_threshold(xp),
            contribution=amounts.get("contribution", 0),
            coins=amounts.get("coins", 0),
            reserved=reserved,
            achievements=achievements,
        )

    # --- ProgressionReader (017 statistics unlocks, 015, 012) --------------------------------------------
    async def level(self, user_id: UUID) -> int:
        return (await self.progress(user_id)).level

    async def has_achievement(self, user_id: UUID, achievement: str) -> bool:
        async with self.database.session() as session:
            found = await session.scalar(
                select(UserAchievement.id).where(
                    UserAchievement.user_id == user_id, UserAchievement.achievement_key == achievement
                )
            )
        return found is not None

    async def achievement_list(self, user_id: UUID, limit: int = 50) -> list[dict[str, str]]:
        """Unlocked achievements, newest first — for profile surfaces (012): key, label, date and (#46) the
        description, icon and rarity a badge shows."""
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        UserAchievement.achievement_key, UserAchievement.unlocked_at, Achievement.definition
                    )
                    .outerjoin(
                        Achievement,
                        (Achievement.key == UserAchievement.achievement_key)
                        & (Achievement.version == UserAchievement.version),
                    )
                    .where(UserAchievement.user_id == user_id)
                    .order_by(UserAchievement.unlocked_at.desc())
                    .limit(limit)
                )
            ).all()
        shares = await self.shares() if self.shares is not None else {}
        return [
            {
                "key": key,
                "label": str((definition or {}).get("label") or key),
                "description": str((definition or {}).get("description") or ""),
                "icon": str((definition or {}).get("icon") or "trophy"),
                "rarity": rarity_of(shares.get(key, 100.0)),
                "unlocked_at": unlocked_at.isoformat(),
            }
            for key, unlocked_at, definition in rows
        ]

    async def xp(self, user_id: UUID) -> int:
        return (await self.progress(user_id)).xp

    async def contribution(self, user_id: UUID) -> int:
        return (await self.progress(user_id)).contribution

    async def coins(self, user_id: UUID) -> int:
        return (await self.progress(user_id)).coins
