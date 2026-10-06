"""« Since your last visit » for progression (027): XP and Coins earned since, the level reached and the
achievements unlocked — one line that sums it up."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from portalab.capabilities.dashboard import ChangeItem
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.modules.gamification.models import LedgerTransaction, UserAchievement
from portalab.modules.gamification.progression.service import ProgressionService


class ProgressionChanges:
    kind = "progression"

    def __init__(self, database: Database, progression: ProgressionService) -> None:
        self.database = database
        self.progression = progression

    async def changes_since(
        self, principal: Principal, since: datetime, limit: int, ctx: LocaleContext
    ) -> Sequence[ChangeItem]:
        user = principal.acting_for or principal.user_id
        if user is None:
            return []
        async with self.database.session() as session:
            gained: dict[str, int] = {
                str(value): int(amount or 0)
                for value, amount in (
                    await session.execute(
                        select(LedgerTransaction.value, func.sum(LedgerTransaction.delta))
                        .where(
                            LedgerTransaction.user_id == user,
                            LedgerTransaction.delta > 0,
                            LedgerTransaction.occurred_at > since,
                        )
                        .group_by(LedgerTransaction.value)
                    )
                ).all()
            }
            last = await session.scalar(
                select(func.max(LedgerTransaction.occurred_at)).where(
                    LedgerTransaction.user_id == user, LedgerTransaction.occurred_at > since
                )
            )
            unlocked = int(
                await session.scalar(
                    select(func.count())
                    .select_from(UserAchievement)
                    .where(UserAchievement.user_id == user, UserAchievement.unlocked_at > since)
                )
                or 0
            )
        xp, coins = int(gained.get("xp") or 0), int(gained.get("coins") or 0)
        if not xp and not coins and not unlocked:
            return []
        level = (await self.progression.progress(user)).level
        return [
            ChangeItem(
                kind="progression",
                occurred_at=last or since,
                ref="/progression",
                title_key="dashboard:summary.progression",
                title_args={"xp": xp, "coins": coins, "level": level, "achievements": unlocked},
                priority=1,
            )
        ]
