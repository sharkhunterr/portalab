"""015 T005 — ``EconomyService.reserve/release/consume`` conformance (the real 013 implementation): a
reservation lowers the available balance without consuming, insufficient Coins are refused, release is a
new transaction, consume is final, requests are idempotent and the balance never goes negative."""

import pytest
from sqlalchemy import text

from portalab.capabilities.economy import EconomyService, InsufficientCoins
from portalab.core.errors import Conflict
from tests.integration.marketplace.conftest import MkHarness

pytestmark = pytest.mark.integration


async def test_reservations(mk: MkHarness) -> None:
    economy = mk.economy.economy
    assert isinstance(economy, EconomyService)
    user = mk.people["ursula"]
    await mk.coins("ursula", 100)
    first = await economy.reserve(user, 60, source_ref="project:x", idempotency_key="k1")
    again = await economy.reserve(user, 60, source_ref="project:x", idempotency_key="k1")
    assert first.id == again.id and await mk.balance("ursula") == 40
    with pytest.raises(InsufficientCoins):
        await economy.reserve(user, 41, source_ref="project:x", idempotency_key="k2")
    assert await mk.balance("ursula") == 40
    released = await economy.release(first.id, reason="test")
    assert released.status == "released" and await mk.balance("ursula") == 100
    second = await economy.reserve(user, 30, source_ref="project:x", idempotency_key="k3")
    consumed = await economy.consume(second.id)
    assert consumed.status == "consumed" and await mk.balance("ursula") == 70
    with pytest.raises(Conflict):
        await economy.release(second.id, reason="too late")
    assert [r.status for r in await economy.reservations([first.id, second.id])] in (
        ["released", "consumed"],
        ["consumed", "released"],
    )
    async with mk.database.session() as session:
        kinds = (
            (
                await session.execute(
                    text("SELECT kind FROM gamification.transactions WHERE user_id = :u ORDER BY seq"),
                    {"u": user},
                )
            )
            .scalars()
            .all()
        )
        negative = await session.scalar(text("SELECT count(*) FROM gamification.balances WHERE amount < 0"))
    assert list(kinds) == ["grant", "reserve", "reserve_release", "reserve", "reserve_consume"]
    assert negative == 0
