"""Issue 443: a master switches its household economy — the ledger's side of it.

To a common pot, what each profile holds (XP, Coins, Contribution, boosters) is duplicated on the master: the
difference between the profile's balance and what its master already holds from it (its rows naming the
profile), once. To dispatched profiles, the master gives back what came from its profiles (down to what it
still holds): each profile keeps its own. The rows name the profile (``profile_id``), publish no reward
event and are never mirrored again; replaying a switch changes nothing."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.ledger.writer import MIRRORED, Entry, LedgerWriter, lock_user
from portalab.modules.gamification.models import Balance, LedgerTransaction


class LedgerPot:
    def __init__(self, database: Database, writer: LedgerWriter, *, clock: Clock | None = None) -> None:
        self.database = database
        self.writer = writer
        self.clock = clock

    async def regroup(self, owner: UUID, profiles: Sequence[UUID], pot: bool) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await lock_user(session, owner)
            for profile in profiles:
                await lock_user(session, profile)
                for value in MIRRORED:
                    held = int(
                        await session.scalar(
                            select(Balance.amount).where(Balance.user_id == profile, Balance.value == value)
                        )
                        or 0
                    )
                    copied = int(
                        await session.scalar(
                            select(func.coalesce(func.sum(LedgerTransaction.delta), 0)).where(
                                LedgerTransaction.user_id == owner,
                                LedgerTransaction.value == value,
                                LedgerTransaction.profile_id == profile,
                            )
                        )
                        or 0
                    )
                    delta = (held if pot else 0) - copied
                    if delta < 0:  # never below what the master still holds
                        master = int(
                            await session.scalar(
                                select(Balance.amount).where(Balance.user_id == owner, Balance.value == value)
                            )
                            or 0
                        )
                        delta = -min(-delta, master)
                    if delta == 0:
                        continue
                    await self.writer.record(
                        session,
                        Entry(
                            user_id=owner,
                            value=value,
                            delta=delta,
                            kind="correction",
                            source_kind="household",
                            source_ref=str(profile),
                            idempotency_key=(
                                f"household-pot:{owner}:{profile}:{value}:{'pot' if pot else 'dispatch'}:"
                                f"{copied}:{held}"
                            ),
                            occurred_at=now,
                            reason="household pot" if pot else "household dispatched",
                            profile_id=profile,
                        ),
                    )
