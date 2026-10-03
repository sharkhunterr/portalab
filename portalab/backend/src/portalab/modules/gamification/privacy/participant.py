"""Privacy participant (T028; CD-005, R12): final deletion releases then **destroys** remaining Coins with
recorded ``destruction`` transactions (never refunded or transferred) — XP and Contribution are zeroed the
same way so the ledger still balances — removes balances, counters, windows,
progress and withheld entries; ledger rows stay bound to the tombstoned user id with no free text. Idempotent
on retry. Export lists the user's own transactions and achievements."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.ledger.writer import Entry, LedgerWriter, lock_user
from portalab.modules.gamification.models import (
    AnomalyFlag,
    AppliedEvent,
    Balance,
    Counter,
    LedgerTransaction,
    QuestProgress,
    Reservation,
    UsageWindow,
    UserAchievement,
    Withheld,
)


class GamificationParticipant:
    def __init__(
        self,
        database: Database,
        writer: LedgerWriter,
        *,
        clock: Clock | None = None,
        leaderboards: Any = None,
    ) -> None:
        self.database = database
        self.writer = writer
        self.clock = clock
        self.leaderboards = leaderboards  # drops the user from snapshots (slice B)

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(LedgerTransaction)
                        .where(LedgerTransaction.user_id == user_id)
                        .order_by(LedgerTransaction.seq)
                    )
                ).scalars()
            )
            achievements = list(
                (
                    await session.execute(select(UserAchievement).where(UserAchievement.user_id == user_id))
                ).scalars()
            )
        records = [
            ExportRecord(
                "gamification.transaction",
                {
                    "value": r.value,
                    "delta": r.delta,
                    "kind": r.kind,
                    "source": r.source_kind,
                    "occurred_at": r.occurred_at.isoformat(),
                },
            )
            for r in rows
        ]
        records += [
            ExportRecord(
                "gamification.achievement",
                {"achievement": a.achievement_key, "unlocked_at": a.unlocked_at.isoformat()},
            )
            for a in achievements
        ]
        return records

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await lock_user(session, user_id)
            reservations = list(
                (
                    await session.execute(
                        select(Reservation)
                        .where(Reservation.user_id == user_id, Reservation.status == "active")
                        .with_for_update()
                    )
                ).scalars()
            )
            for reservation in reservations:
                recorded = await self.writer.record(
                    session,
                    Entry(
                        user_id=user_id,
                        value="coins",
                        delta=reservation.amount,
                        kind="reserve_release",
                        source_kind="system",
                        source_ref=reservation.source_ref,
                        idempotency_key=f"reserve_release:{reservation.id}",
                        occurred_at=now,
                        reverses_transaction_id=reservation.reserve_tx_id,
                    ),
                )
                reservation.status, reservation.resolution_tx_id, reservation.resolved_at = (
                    "destroyed",
                    recorded.transaction.id,
                    now,
                )
            for value in ("coins", "xp", "contribution"):  # Coins destroyed; the other values zeroed alike
                balance = await session.get(Balance, (user_id, value))
                if balance is not None and balance.amount > 0:
                    await self.writer.record(
                        session,
                        Entry(
                            user_id=user_id,
                            value=value,
                            delta=-balance.amount,
                            kind="destruction",
                            source_kind="system",
                            source_ref="account_deletion",
                            idempotency_key=f"destruction:{user_id}:{value}:{balance.last_seq}",
                            occurred_at=now,
                        ),
                    )
            for model in (
                Balance,
                Counter,
                UsageWindow,
                UserAchievement,
                QuestProgress,
                Withheld,
                AnomalyFlag,
                AppliedEvent,
            ):
                await session.execute(delete(model).where(model.user_id == user_id))
        if self.leaderboards is not None:
            await self.leaderboards.forget(user_id)
