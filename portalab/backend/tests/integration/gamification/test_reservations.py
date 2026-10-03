"""013 T032 (F3, CD-008) — Coin reservations for funding: available balance excludes active reservations
and never goes negative; release returns Coins, consume keeps them spent; idempotent; a caller session makes
the operation atomic with the caller's own writes; final deletion destroys reservations."""

import pytest
from sqlalchemy import text

from portalab.capabilities.economy import InsufficientCoins
from tests.integration.gamification.conftest import GamHarness

pytestmark = pytest.mark.integration


async def test_reserve_release_consume(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    economy = gm.module.economy
    await gm.module.rewards.grant_manual(
        gm.p("boss"), user, "coins", 100, reason="seed", idempotency_key="seed"
    )
    first = await economy.reserve(user, 60, source_ref="project:1", idempotency_key="f1")
    assert (await economy.reserve(user, 60, source_ref="project:1", idempotency_key="f1")).id == first.id
    assert await economy.balance(user, "coins") == 40 and await economy.reserved(user) == 60
    with pytest.raises(InsufficientCoins):
        await economy.reserve(user, 41, source_ref="project:2", idempotency_key="f2")
    released = await economy.release(first.id, reason="project failed")
    assert released.status == "released" and await economy.balance(user, "coins") == 100
    second = await economy.reserve(user, 70, source_ref="project:3", idempotency_key="f3")
    consumed = await economy.consume(second.id)
    assert (
        consumed.status == "consumed"
        and await economy.balance(user, "coins") == 30
        and await economy.reserved(user) == 0
    )
    assert (await economy.consume(second.id)).status == "consumed"


async def test_caller_session_is_atomic(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    await gm.module.rewards.grant_manual(
        gm.p("boss"), user, "coins", 10, reason="seed", idempotency_key="seed"
    )
    with pytest.raises(RuntimeError):
        async with gm.database.unit_of_work() as uow:
            await gm.module.economy.spend(
                user,
                10,
                reason="buy",
                source_kind="marketplace",
                source_ref="p",
                idempotency_key="atomic",
                session=uow.session,
            )
            raise RuntimeError("the marketplace failed afterwards")
    assert await gm.module.economy.balance(user, "coins") == 10


async def test_deletion_destroys_reservations(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    await gm.module.rewards.grant_manual(
        gm.p("boss"), user, "coins", 80, reason="seed", idempotency_key="seed"
    )
    await gm.module.economy.reserve(user, 50, source_ref="project:9", idempotency_key="r9")
    from portalab.modules.gamification.privacy.participant import GamificationParticipant

    await GamificationParticipant(gm.database, gm.module.writer, clock=gm.clock).erase(user, "final")
    async with gm.database.session() as session:
        statuses = (
            (await session.execute(text("SELECT status FROM gamification.reservations"))).scalars().all()
        )
        net = await session.scalar(
            text("SELECT sum(delta) FROM gamification.transactions WHERE user_id = :u AND value = 'coins'"),
            {"u": user},
        )
    assert statuses == ["destroyed"] and net == 0
