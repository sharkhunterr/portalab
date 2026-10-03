"""013 T005 — balances always equal the sum of the ledger after random operation sequences; concurrent
spends never overdraw; a failure mid-transaction leaves ledger, balance and outbox untouched."""

import asyncio
import random

import pytest
from sqlalchemy import func, select, text

from portalab.capabilities.economy import InsufficientCoins
from portalab.modules.gamification.ledger.writer import Entry
from portalab.modules.gamification.models import LedgerTransaction
from portalab.modules.gamification.verify.verifier import verify
from tests.integration.gamification.conftest import SYSTEM, GamHarness

pytestmark = pytest.mark.integration


async def grant(gm: GamHarness, user: object, amount: int, key: str) -> None:
    await gm.module.rewards.grant_manual(
        gm.p("boss"),
        user,
        "coins",
        amount,
        reason="test grant",
        idempotency_key=key,  # type: ignore[arg-type]
    )


async def test_random_sequences_stay_consistent(gm: GamHarness) -> None:
    rng = random.Random(13)  # noqa: S311 — deterministic test data
    user = gm.people["ursula"]
    spent: list[object] = []
    for step in range(60):
        action = rng.choice(["grant", "spend", "refund"])
        if action == "grant":
            await grant(gm, user, rng.randint(1, 50), f"g{step}")
        elif action == "spend":
            try:
                tx = await gm.module.economy.spend(
                    user,
                    rng.randint(1, 60),
                    reason="buy",
                    source_kind="marketplace",
                    source_ref=f"p{step}",
                    idempotency_key=f"s{step}",
                )
                spent.append(tx.id)
            except InsufficientCoins:
                pass
        elif spent:
            tx_id = spent.pop(rng.randrange(len(spent)))
            await gm.module.economy.refund(tx_id, reason="refund", idempotency_key=f"r{step}")  # type: ignore[arg-type]
        report = await verify(gm.database)
        assert report.ok, report.drifts
    assert await gm.balance(user, "coins") >= 0


async def test_concurrent_spends_cannot_overdraw(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    await grant(gm, user, 100, "seed")

    async def attempt(index: int) -> bool:
        try:
            await gm.module.economy.spend(
                user,
                30,
                reason="buy",
                source_kind="marketplace",
                source_ref=f"c{index}",
                idempotency_key=f"c{index}",
            )
            return True
        except InsufficientCoins:
            return False

    results = await asyncio.gather(*(attempt(i) for i in range(8)))
    assert results.count(True) == 3
    assert await gm.balance(user, "coins") == 10
    assert (await verify(gm.database)).ok


async def test_failure_mid_transaction_leaves_nothing(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    with pytest.raises(RuntimeError):
        async with gm.database.unit_of_work() as uow:
            await gm.module.writer.record(
                uow.session,
                Entry(
                    user_id=user,
                    value="xp",
                    delta=10,
                    kind="grant",
                    source_kind="system",
                    idempotency_key="boom",
                    occurred_at=gm.clock.now(),
                ),
            )
            raise RuntimeError("crash after the ledger write")
    async with gm.database.session() as session:
        count = await session.scalar(select(func.count()).select_from(LedgerTransaction))
        outbox = await session.scalar(
            text("SELECT count(*) FROM events.events WHERE type = 'reward.granted'")
        )
    assert count == 0 and outbox == 0 and await gm.balance(user) == 0
    assert SYSTEM.channel == "system"
