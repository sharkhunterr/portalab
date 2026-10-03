"""``LedgerWriter`` (T008): the **single write path** of the economy, inside the caller's transaction.

1. insert the transaction — an existing ``idempotency_key`` returns the original row (no second effect);
2. update the balance: credits upsert, debits are guarded (``amount + delta >= 0``) — an overdraft raises
   ``InsufficientCoins`` and the caller's transaction rolls back entirely;
3. for XP, derive the level from the curve and emit one ``user.level_up`` when it rises;
4. publish the matching event through the outbox in the same transaction.
Rows are never updated or deleted (database triggers); corrections are new rows."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.economy import InsufficientCoins, Transaction
from portalab.core.authz_port import Principal
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.ids import new_id
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.levels.service import LevelService
from portalab.modules.gamification.models import Balance, LedgerTransaction

GRANT_KINDS = ("grant", "manual", "correction")
EVENTS = {
    "spend": "economy.coins_spent",
    "refund": "economy.coins_refunded",
    "destruction": "economy.coins_destroyed",
}


@dataclass(frozen=True, slots=True)
class Entry:
    user_id: UUID
    value: str
    delta: int
    kind: str
    source_kind: str
    idempotency_key: str
    occurred_at: datetime
    source_ref: str | None = None
    rule_key: str | None = None
    rule_version: int | None = None
    trigger_event_id: UUID | None = None
    base_amount: int = 0
    multiplier: float = 1.0
    modifiers: dict[str, Any] = field(default_factory=dict)
    guards: dict[str, Any] = field(default_factory=dict)
    actor_user_id: UUID | None = None
    reason: str | None = None
    reverses_transaction_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class Recorded:
    transaction: Transaction
    duplicate: bool = False
    level_up: int | None = None


def to_transaction(row: LedgerTransaction, duplicate: bool = False) -> Transaction:
    return Transaction(
        id=row.id,
        seq=row.seq,
        user_id=row.user_id,
        value=row.value,  # type: ignore[arg-type]
        delta=row.delta,
        kind=row.kind,
        source_kind=row.source_kind,
        source_ref=row.source_ref,
        occurred_at=row.occurred_at,
        recorded_at=row.recorded_at,
        rule_key=row.rule_key,
        rule_version=row.rule_version,
        reason=row.reason,
        reverses_transaction_id=row.reverses_transaction_id,
        duplicate=duplicate,
    )


async def lock_user(session: AsyncSession, user: UUID) -> None:
    """Per-user serialization of economy writes (R8): a transaction-scoped advisory lock."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"gamification:{user}"}
    )


class LedgerWriter:
    def __init__(self, events: EventPublisher, levels: LevelService, *, clock: Clock | None = None) -> None:
        self.events = events
        self.levels = levels
        self.clock = clock

    async def record(self, session: AsyncSession, entry: Entry) -> Recorded:
        if entry.value not in ("xp", "contribution", "coins"):
            raise ValueError("unknown value")
        now = utc_now(self.clock)
        values = {
            "id": new_id(),
            "user_id": entry.user_id,
            "value": entry.value,
            "delta": entry.delta,
            "kind": entry.kind,
            "source_kind": entry.source_kind,
            "source_ref": entry.source_ref,
            "rule_key": entry.rule_key,
            "rule_version": entry.rule_version,
            "trigger_event_id": entry.trigger_event_id,
            "idempotency_key": entry.idempotency_key,
            "base_amount": entry.base_amount,
            "multiplier": entry.multiplier,
            "modifiers": entry.modifiers,
            "guards": entry.guards,
            "actor_user_id": entry.actor_user_id,
            "reason": (entry.reason or "")[:200] or None,
            "reverses_transaction_id": entry.reverses_transaction_id,
            "occurred_at": entry.occurred_at,
            "recorded_at": now,
        }
        inserted = (
            await session.execute(
                insert(LedgerTransaction)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["idempotency_key"])
                .returning(LedgerTransaction.id)
            )
        ).scalar_one_or_none()
        if inserted is None:
            existing = (
                await session.execute(
                    select(LedgerTransaction).where(
                        LedgerTransaction.idempotency_key == entry.idempotency_key
                    )
                )
            ).scalar_one()
            return Recorded(to_transaction(existing, duplicate=True), duplicate=True)
        row = (
            await session.execute(select(LedgerTransaction).where(LedgerTransaction.id == inserted))
        ).scalar_one()
        amount = await self._balance(session, row)
        level_up = await self._level(session, row, amount) if row.value == "xp" else None
        await self._publish(session, row, level_up)
        return Recorded(to_transaction(row), level_up=level_up)

    async def _balance(self, session: AsyncSession, row: LedgerTransaction) -> int:
        if row.delta >= 0:
            statement = insert(Balance).values(
                user_id=row.user_id, value=row.value, amount=row.delta, last_seq=row.seq
            )
            statement = statement.on_conflict_do_update(
                index_elements=[Balance.user_id, Balance.value],
                set_={"amount": Balance.amount + row.delta, "last_seq": row.seq},
            )
            return int((await session.execute(statement.returning(Balance.amount))).scalar_one())
        guarded = (
            await session.execute(
                update(Balance)
                .where(
                    Balance.user_id == row.user_id,
                    Balance.value == row.value,
                    Balance.amount + row.delta >= 0,
                )
                .values(amount=Balance.amount + row.delta, last_seq=row.seq)
                .returning(Balance.amount)
            )
        ).scalar_one_or_none()
        if guarded is None:
            raise InsufficientCoins(
                "Not enough Coins for this operation." if row.value == "coins" else "Not enough balance.",
                code="economy.insufficient_coins" if row.value == "coins" else "economy.insufficient_balance",
            )
        return int(guarded)

    async def _level(self, session: AsyncSession, row: LedgerTransaction, amount: int) -> int | None:
        curve = await self.levels.curve(session)
        level = curve.level_for(amount)
        balance = await session.get(Balance, (row.user_id, "xp"), with_for_update=True)
        assert balance is not None
        previous = (
            balance.level if balance.level is not None and balance.curve_version == curve.version else None
        )
        if previous is None:
            previous = curve.level_for(amount - row.delta)
        balance.level, balance.curve_version = level, curve.version
        if level > previous and row.delta > 0:
            await self.events.publish(
                session,
                "user.level_up",
                {"level": level},
                occurred_at=row.occurred_at,
                actor=Principal(user_id=row.user_id, channel="system"),
                subject=SubjectRef("user", str(row.user_id)),
                dedup_key=f"user.level_up:{row.user_id}:{level}",
            )
            return level
        return None

    async def _publish(self, session: AsyncSession, row: LedgerTransaction, level_up: int | None) -> None:
        if row.kind in ("grant", "manual") and row.delta > 0:
            name = "reward.granted"
            payload: dict[str, Any] = {"value": row.value, "amount": row.delta, "source": row.source_kind}
            if row.rule_key:
                payload |= {"rule": row.rule_key, "version": row.rule_version}
        elif row.kind in EVENTS and row.value == "coins":
            name = EVENTS[row.kind]
            payload = {"amount": abs(row.delta), "source": row.source_kind}
        else:
            return
        await self.events.publish(
            session,
            name,
            payload,
            occurred_at=row.occurred_at,
            actor=Principal(user_id=row.user_id, channel="system"),
            subject=SubjectRef("user", str(row.user_id)),
            dedup_key=f"{name}:{row.id}",
        )
