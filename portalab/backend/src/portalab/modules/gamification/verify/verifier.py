"""Ledger verification (T011): balances recomputed from the ledger — any drift is reported (read-only).
Exposed as ``portalab economy verify`` and ``GET /admin/economy/verify``."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, select

from portalab.core.db import Database
from portalab.modules.gamification.models import Balance, LedgerTransaction
from portalab.modules.gamification.observability import metrics


@dataclass(frozen=True, slots=True)
class Drift:
    user_id: UUID
    value: str
    ledger: int
    balance: int


@dataclass(frozen=True, slots=True)
class Report:
    checked: int
    drifts: list[Drift] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.drifts


async def verify(database: Database) -> Report:
    async with database.session() as session:
        sums = {
            (user, value): int(total)
            for user, value, total in (
                await session.execute(
                    select(
                        LedgerTransaction.user_id, LedgerTransaction.value, func.sum(LedgerTransaction.delta)
                    ).group_by(LedgerTransaction.user_id, LedgerTransaction.value)
                )
            ).all()
        }
        balances = {
            (user, value): int(amount)
            for user, value, amount in (
                await session.execute(select(Balance.user_id, Balance.value, Balance.amount))
            ).all()
        }
    drifts = [
        Drift(user, value, sums.get((user, value), 0), balances.get((user, value), 0))
        for user, value in sorted(set(sums) | set(balances), key=lambda k: (str(k[0]), k[1]))
        if sums.get((user, value), 0) != balances.get((user, value), 0)
    ]
    metrics.gauge("gamification.ledger.drift", len(drifts))
    return Report(len(set(sums) | set(balances)), drifts)
