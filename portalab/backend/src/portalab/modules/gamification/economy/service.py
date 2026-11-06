"""``EconomyService`` (T010, T032): spend / refund / reserve / release / consume Coins for other modules
(Marketplace 015, Community funding), plus balance and history.

Every operation is one transaction — the caller's when it passes ``session`` (atomic multi-module
operations), else its own — serialized per user, idempotent by key, and never makes a balance negative.
A refund or a release is a new transaction referencing the original; Coins can never be created from money
and values are never converted into one another."""

import base64
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.economy import HistoryPage, InsufficientCoins, Reservation, Transaction, Value
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.ledger.writer import Entry, LedgerWriter, lock_user, to_transaction
from portalab.modules.gamification.models import Balance, LedgerTransaction
from portalab.modules.gamification.models import Reservation as ReservationRow
from portalab.modules.gamification.observability import metrics

SPEND_SOURCES = ("marketplace", "community_funding", "system", "requests")  # issue 363: a priced request
T = TypeVar("T")


def encode_cursor(seq: int) -> str:
    return base64.urlsafe_b64encode(str(seq).encode()).decode()


def decode_cursor(cursor: str | None) -> int | None:
    if not cursor:
        return None
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except ValueError as exc:
        raise ValidationFailed("Invalid cursor.", code="economy.invalid_cursor") from exc


def _reservation(row: ReservationRow) -> Reservation:
    return Reservation(row.id, row.user_id, row.amount, row.source_kind, row.source_ref, row.status)  # type: ignore[arg-type]


class EconomyServiceImpl:
    def __init__(self, database: Database, writer: LedgerWriter, *, clock: Clock | None = None) -> None:
        self.database = database
        self.writer = writer
        self.clock = clock

    @asynccontextmanager
    async def _session(self, session: AsyncSession | None) -> AsyncIterator[AsyncSession]:
        if session is not None:
            yield session
            return
        async with self.database.unit_of_work() as uow:
            yield uow.session

    async def _run(self, session: AsyncSession | None, work: Callable[[AsyncSession], Awaitable[T]]) -> T:
        async with self._session(session) as active:
            return await work(active)

    # --- spending ----------------------------------------------------------------------------------------
    async def spend(
        self,
        user: UUID,
        amount: int,
        *,
        reason: str,
        source_kind: str,
        source_ref: str,
        idempotency_key: str,
        session: Any | None = None,
    ) -> Transaction:
        if amount <= 0:
            raise ValidationFailed("Spend a positive amount.", code="economy.invalid_amount")
        if source_kind not in SPEND_SOURCES:
            raise ValidationFailed("Unknown spending source.", code="economy.invalid_source")

        async def work(active: AsyncSession) -> Transaction:
            await lock_user(active, user)
            recorded = await self.writer.record(
                active,
                Entry(
                    user_id=user,
                    value="coins",
                    delta=-amount,
                    kind="spend",
                    source_kind=source_kind,
                    source_ref=source_ref,
                    idempotency_key=f"spend:{idempotency_key}",
                    occurred_at=utc_now(self.clock),
                    reason=reason,
                ),
            )
            return recorded.transaction

        try:
            transaction = await self._run(session, work)
        except InsufficientCoins:
            metrics.increment("gamification.spend.refused")
            raise
        metrics.increment("gamification.spend.ok")
        return transaction

    async def refund(
        self,
        transaction_id: UUID,
        *,
        reason: str,
        idempotency_key: str,
        session: Any | None = None,
        amount: int | None = None,
    ) -> Transaction:
        async def work(active: AsyncSession) -> Transaction:
            original = await active.get(LedgerTransaction, transaction_id)
            if original is None or original.kind != "spend":
                raise NotFound("This spending does not exist.", code="economy.transaction_not_found")
            await lock_user(active, original.user_id)
            refunded = int(
                await active.scalar(
                    select(func.coalesce(func.sum(LedgerTransaction.delta), 0)).where(
                        LedgerTransaction.reverses_transaction_id == original.id,
                        LedgerTransaction.kind == "refund",
                    )
                )
                or 0
            )
            key = f"refund:{idempotency_key}"
            existing = (
                await active.execute(
                    select(LedgerTransaction).where(LedgerTransaction.idempotency_key == key)
                )
            ).scalar_one_or_none()
            if existing is not None:
                return to_transaction(existing, duplicate=True)
            remaining = -original.delta - refunded
            if remaining <= 0:
                raise Conflict("This spending was already refunded.", code="economy.already_refunded")
            if amount is not None:
                if amount <= 0:
                    raise ValidationFailed("Refund a positive amount.", code="economy.invalid_amount")
                remaining = min(remaining, amount)
            recorded = await self.writer.record(
                active,
                Entry(
                    user_id=original.user_id,
                    value="coins",
                    delta=remaining,
                    kind="refund",
                    source_kind=original.source_kind,
                    source_ref=original.source_ref,
                    idempotency_key=key,
                    occurred_at=utc_now(self.clock),
                    reason=reason,
                    reverses_transaction_id=original.id,
                ),
            )
            return recorded.transaction

        return await self._run(session, work)

    # --- reservations (CD-008) ---------------------------------------------------------------------------
    async def reserve(
        self,
        user: UUID,
        amount: int,
        *,
        source_ref: str,
        idempotency_key: str,
        source_kind: str = "community_funding",
        session: Any | None = None,
    ) -> Reservation:
        if amount <= 0:
            raise ValidationFailed("Reserve a positive amount.", code="economy.invalid_amount")

        async def work(active: AsyncSession) -> Reservation:
            await lock_user(active, user)
            key = f"reserve:{idempotency_key}"
            existing = (
                await active.execute(select(ReservationRow).where(ReservationRow.idempotency_key == key))
            ).scalar_one_or_none()
            if existing is not None:
                return _reservation(existing)
            recorded = await self.writer.record(
                active,
                Entry(
                    user_id=user,
                    value="coins",
                    delta=-amount,
                    kind="reserve",
                    source_kind=source_kind,
                    source_ref=source_ref,
                    idempotency_key=key,
                    occurred_at=utc_now(self.clock),
                ),
            )
            row = ReservationRow(
                user_id=user,
                amount=amount,
                source_kind=source_kind,
                source_ref=source_ref,
                idempotency_key=key,
                status="active",
                reserve_tx_id=recorded.transaction.id,
                created_at=utc_now(self.clock),
            )
            active.add(row)
            await active.flush()
            return _reservation(row)

        return await self._run(session, work)

    async def _resolve(
        self, reservation_id: UUID, status: str, kind: str, reason: str | None, session: Any | None
    ) -> Reservation:
        async def work(active: AsyncSession) -> Reservation:
            row = await active.get(ReservationRow, reservation_id, with_for_update=True)
            if row is None:
                raise NotFound("This reservation does not exist.", code="economy.reservation_not_found")
            if row.status == status:
                return _reservation(row)
            if row.status != "active":
                raise Conflict("This reservation is already settled.", code="economy.reservation_settled")
            await lock_user(active, row.user_id)
            recorded = await self.writer.record(
                active,
                Entry(
                    user_id=row.user_id,
                    value="coins",
                    delta=row.amount if kind == "reserve_release" else 0,
                    kind=kind,
                    source_kind=row.source_kind,
                    source_ref=row.source_ref,
                    idempotency_key=f"{kind}:{row.id}",
                    occurred_at=utc_now(self.clock),
                    reason=reason,
                    reverses_transaction_id=row.reserve_tx_id,
                ),
            )
            row.status, row.resolution_tx_id, row.resolved_at = (
                status,
                recorded.transaction.id,
                utc_now(self.clock),
            )
            return _reservation(row)

        return await self._run(session, work)

    async def release(self, reservation_id: UUID, *, reason: str, session: Any | None = None) -> Reservation:
        return await self._resolve(reservation_id, "released", "reserve_release", reason, session)

    async def consume(self, reservation_id: UUID, *, session: Any | None = None) -> Reservation:
        return await self._resolve(reservation_id, "consumed", "reserve_consume", None, session)

    # --- reads -------------------------------------------------------------------------------------------
    async def reservations(self, ids: Sequence[UUID]) -> list[Reservation]:
        """Current state of the given reservations (unknown ids are skipped) — for reconciliation."""
        if not ids:
            return []
        async with self.database.session() as session:
            rows = (
                await session.execute(select(ReservationRow).where(ReservationRow.id.in_(list(ids))))
            ).scalars()
            return [_reservation(r) for r in rows]

    async def balance(self, user: UUID, value: Value) -> int:
        async with self.database.session() as session:
            amount = await session.scalar(
                select(Balance.amount).where(Balance.user_id == user, Balance.value == value)
            )
        return int(amount or 0)

    async def reserved(self, user: UUID) -> int:
        async with self.database.session() as session:
            total = await session.scalar(
                select(func.coalesce(func.sum(ReservationRow.amount), 0)).where(
                    ReservationRow.user_id == user, ReservationRow.status == "active"
                )
            )
        return int(total or 0)

    async def history(
        self, user: UUID, *, value: Value | None = None, cursor: str | None = None, limit: int = 50
    ) -> HistoryPage:
        before = decode_cursor(cursor)
        statement = select(LedgerTransaction).where(LedgerTransaction.user_id == user)
        if value is not None:
            statement = statement.where(LedgerTransaction.value == value)
        if before is not None:
            statement = statement.where(LedgerTransaction.seq < before)
        statement = statement.order_by(LedgerTransaction.seq.desc()).limit(max(1, min(limit, 200)) + 1)
        async with self.database.session() as session:
            rows = list((await session.execute(statement)).scalars())
        page = rows[:limit]
        return HistoryPage(
            [to_transaction(r) for r in page],
            encode_cursor(page[-1].seq) if len(rows) > limit and page else None,
        )
