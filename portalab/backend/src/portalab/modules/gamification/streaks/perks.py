"""Perks bought in the shop (#54, #55).

* **Streak freezes** — each one covers one missed day of a play streak: when a member's streak was alive
  the day before yesterday and yesterday has no counted day, a freeze they own is used (yesterday becomes
  a ``frozen`` streak day) and the streak goes on. Checked every hour, once the day is over (economy time
  zone). Those available are the ones bought less the days frozen.
* **Boosts** — a factor on some gains (XP by default) for a time; a boost bought while another runs starts
  when it ends. Provided as a reward modifier (instance ``boost``), so it combines with campaigns, streaks
  and the pace under the global boost cap.
"""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.economy import Modifier, Value
from portalab.capabilities.events import Envelope
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.ledger.writer import Entry
from portalab.modules.gamification.models import Boost, FreezeGrant, StreakDay
from portalab.modules.gamification.streaks.service import Streaks

MAX_FACTOR = 5.0
MAX_HOURS = 24 * 30
MAX_CREDIT = 10_000


class Perks:
    def __init__(
        self, database: Database, streaks: Streaks, clock: Clock | None = None, writer: Any | None = None
    ) -> None:
        self.database = database
        self.streaks = streaks
        self.clock = clock
        self.writer = writer

    # --- what the shop grants -------------------------------------------------------------------------
    async def grant_freezes(self, user: UUID, count: int, source: str) -> None:
        if count <= 0:
            return
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(FreezeGrant)
                .values(
                    source=source[:120], user_id=user, count=min(count, 100), granted_at=utc_now(self.clock)
                )
                .on_conflict_do_nothing(index_elements=["source"])
            )

    async def grant_boost(
        self, user: UUID, factor: float, hours: float, values: Sequence[str], source: str
    ) -> None:
        if factor <= 1 or hours <= 0:
            return
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            last = (
                await uow.session.execute(
                    select(func.max(Boost.ends_at)).where(Boost.user_id == user, Boost.ends_at > now)
                )
            ).scalar_one_or_none()
            starts = max(now, last) if last else now
            await uow.session.execute(
                insert(Boost)
                .values(
                    source=source[:120],
                    user_id=user,
                    factor=min(float(factor), MAX_FACTOR),
                    gains=[str(v) for v in values] or ["xp"],
                    starts_at=starts,
                    ends_at=starts + timedelta(hours=min(float(hours), MAX_HOURS)),
                )
                .on_conflict_do_nothing(index_elements=["source"])
            )

    async def credit_coins(self, user: UUID, amount: int, source: str, idempotency_key: str) -> None:
        """#81: Coins the shop gives back outside a purchase (a duplicate in an offered booster)."""
        if amount <= 0 or self.writer is None:
            return
        async with self.database.unit_of_work() as uow:
            await self.writer.record(
                uow.session,
                Entry(
                    user_id=user,
                    value="coins",
                    delta=min(int(amount), MAX_CREDIT),
                    kind="grant",
                    source_kind="marketplace",
                    source_ref=source[:200],
                    idempotency_key=f"perk:{idempotency_key}"[:200],
                    occurred_at=utc_now(self.clock),
                    base_amount=min(int(amount), MAX_CREDIT),
                ),
            )

    # --- boosts as a reward modifier --------------------------------------------------------------------
    async def active_boost(self, user: UUID, at: datetime) -> Boost | None:
        async with self.database.session() as session:
            return (
                await session.execute(
                    select(Boost)
                    .where(Boost.user_id == user, Boost.starts_at <= at, Boost.ends_at > at)
                    .order_by(Boost.factor.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

    async def modifiers_for(
        self, user: UUID, event: Envelope, value: Value, at: datetime
    ) -> Sequence[Modifier]:
        boost = await self.active_boost(user, at)
        if boost is None or value not in (boost.gains or ["xp"]):
            return []
        return [Modifier(f"boost:{boost.source}", float(boost.factor))]

    # --- freezes ----------------------------------------------------------------------------------------
    async def freezes_available(self, user: UUID) -> int:
        async with self.database.session() as session:
            granted = (
                await session.execute(
                    select(func.coalesce(func.sum(FreezeGrant.count), 0)).where(FreezeGrant.user_id == user)
                )
            ).scalar_one()
            used = (
                await session.execute(
                    select(func.count()).where(StreakDay.user_id == user, StreakDay.frozen.is_(True))
                )
            ).scalar_one()
        return max(0, int(granted) - int(used))

    async def apply_freezes(self, at: datetime | None = None) -> int:
        """Cover yesterday for every member whose streak was alive the day before and who owns a freeze."""
        if not self.streaks.settings().enabled:
            return 0
        now = at or utc_now(self.clock)
        yesterday: date = self.streaks._day(now) - timedelta(days=1)
        async with self.database.session() as session:
            owners = list((await session.execute(select(FreezeGrant.user_id).distinct())).scalars())
        frozen = 0
        for user in owners:
            if await self.freezes_available(user) <= 0:
                continue
            if await self.streaks.length(user, yesterday) > 0:
                continue  # yesterday counted (or already frozen)
            if await self.streaks.length(user, yesterday - timedelta(days=1)) <= 0:
                continue  # no streak to keep
            async with self.database.unit_of_work() as uow:
                done = await uow.session.execute(
                    insert(StreakDay)
                    .values(user_id=user, day=yesterday, frozen=True)
                    .on_conflict_do_nothing()
                )
            frozen += int(getattr(done, "rowcount", 0) or 0)
        return frozen

    # --- for the member's pages -------------------------------------------------------------------------
    async def state(self, user: UUID, at: datetime | None = None) -> dict[str, Any]:
        now = at or utc_now(self.clock)
        boost = await self.active_boost(user, now)
        async with self.database.session() as session:
            queued_until = (
                await session.execute(
                    select(func.max(Boost.ends_at)).where(Boost.user_id == user, Boost.ends_at > now)
                )
            ).scalar_one_or_none()
            last_frozen = (
                await session.execute(
                    select(func.max(StreakDay.day)).where(
                        StreakDay.user_id == user, StreakDay.frozen.is_(True)
                    )
                )
            ).scalar_one_or_none()
        return {
            "boost": (
                {
                    "factor": float(boost.factor),
                    "gains": list(boost.gains or ["xp"]),
                    "ends_at": boost.ends_at.isoformat(),
                    "until": queued_until.isoformat() if queued_until else boost.ends_at.isoformat(),
                }
                if boost is not None
                else None
            ),
            "freezes": await self.freezes_available(user),
            "last_frozen": last_frozen.isoformat() if last_frozen else None,
        }
