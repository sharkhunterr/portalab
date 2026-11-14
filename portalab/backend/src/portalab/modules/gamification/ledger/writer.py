"""``LedgerWriter`` (T008): the **single write path** of the economy, inside the caller's transaction.

1. insert the transaction — an existing ``idempotency_key`` returns the original row (no second effect);
2. update the balance: credits upsert, debits are guarded (``amount + delta >= 0``) — an overdraft raises
   ``InsufficientCoins`` and the caller's transaction rolls back entirely;
3. for XP, derive the level from the curve and emit one ``user.level_up`` when it rises;
4. publish the matching event through the outbox in the same transaction;
5. for XP and Coins, queue a ``progression.changed`` live notification to the owner only (spec 027 R6), so
   the header updates without polling — and never on rollback, since it shares the transaction;
6. 032: for a household profile, record the same XP, Contribution or Coins once more for its master, in the
   same transaction (the master's balances are the household's): a debit the household cannot cover refuses
   a spend or a reservation, and an administrator's correction is mirrored up to what the master holds; the
   copy publishes no reward event (it rewards nothing twice).
Rows are never updated or deleted (database triggers); corrections are new rows."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.economy import InsufficientCoins, Transaction
from portalab.capabilities.household import Household
from portalab.core.authz_port import Principal
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.ids import new_id
from portalab.core.live import publish_live
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.levels.service import LevelService
from portalab.modules.gamification.models import Balance, LedgerTransaction

GRANT_KINDS = ("grant", "manual", "correction")
EVENTS = {
    "spend": "economy.coins_spent",
    "refund": "economy.coins_refunded",
    "destruction": "economy.coins_destroyed",
}
MIRRORED = ("xp", "contribution", "coins")
REFUSED_SHORT = ("spend", "reserve")  # a household that cannot cover them refuses them


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
    profile_id: UUID | None = None  # 032: set on a master's copy of a profile's row


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
        self.household: Callable[[], Household | None] = lambda: None  # 032: wired by the module

    async def record(self, session: AsyncSession, entry: Entry) -> Recorded:
        if entry.value not in ("xp", "contribution", "coins", "booster"):
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
            "profile_id": entry.profile_id,
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
        if entry.profile_id is None:
            await self._publish(session, row, level_up)
        if row.value in ("xp", "coins"):
            await self._live(session, row, level_up)
        if entry.profile_id is None and row.value in MIRRORED:
            await self._mirror(session, entry)
        return Recorded(to_transaction(row), level_up=level_up)

    async def _mirror(self, session: AsyncSession, entry: Entry) -> None:
        """032: the same amount for the profile's household master (once: the copy's key derives from the
        profile row's)."""
        household = self.household()
        owner = await household.owner_of(entry.user_id) if household is not None else None
        if owner is None:
            return
        await lock_user(session, owner)
        delta = entry.delta
        if delta < 0 and entry.kind not in REFUSED_SHORT:
            held = await session.scalar(
                select(Balance.amount).where(Balance.user_id == owner, Balance.value == entry.value)
            )
            delta = -min(-delta, int(held or 0))
            if delta == 0:
                return
        digest = hashlib.sha256(entry.idempotency_key.encode("utf-8")).hexdigest()
        await self.record(
            session,
            replace(
                entry,
                user_id=owner,
                delta=delta,
                idempotency_key=f"household:{digest}",
                reverses_transaction_id=None,
                profile_id=entry.user_id,
            ),
        )

    async def _live(self, session: AsyncSession, row: LedgerTransaction, level_up: int | None) -> None:
        rows = (
            await session.execute(
                select(Balance.value, Balance.amount).where(
                    Balance.user_id == row.user_id, Balance.value.in_(("xp", "coins"))
                )
            )
        ).all()
        amounts: dict[str, int] = {str(value): int(amount) for value, amount in rows}
        xp, coins = int(amounts.get("xp", 0)), int(amounts.get("coins", 0))
        curve = await self.levels.curve(session)
        level = curve.level_for(xp)
        await publish_live(
            session,
            topic="progression.changed",
            payload={
                "xp": xp,
                "level": level,
                "level_floor": curve.threshold(level),
                "next_level_at": curve.next_threshold(xp),
                "coins": coins,
                "delta_xp": row.delta if row.value == "xp" else 0,
                "delta_coins": row.delta if row.value == "coins" else 0,
                "level_up": level_up is not None,
            },
            audience_user_id=row.user_id,
            clock=self.clock,
        )

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
