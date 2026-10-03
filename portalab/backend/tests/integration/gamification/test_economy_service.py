"""013 T009 — spend/refund atomic and idempotent, overspend refused without side effects, refunds are new
transactions, history paginated and owner-only; no path creates Coins from money."""

import pytest
from httpx import AsyncClient

from portalab.capabilities.economy import ECONOMY, EconomyService, InsufficientCoins
from portalab.core.errors import Conflict, ValidationFailed
from tests.integration.gamification.conftest import GamHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_spend_refund_idempotency(gm: GamHarness) -> None:
    user = gm.people["ursula"]
    service = gm.ev.full.identity.capabilities.system_providers(ECONOMY)[0].provider
    assert isinstance(service, EconomyService)
    assert not hasattr(service, "convert") and not hasattr(service, "buy_coins")
    await gm.module.rewards.grant_manual(
        gm.p("boss"), user, "coins", 50, reason="seed", idempotency_key="seed"
    )
    spent = await service.spend(
        user, 30, reason="poster", source_kind="marketplace", source_ref="item:1", idempotency_key="o1"
    )
    again = await service.spend(
        user, 30, reason="poster", source_kind="marketplace", source_ref="item:1", idempotency_key="o1"
    )
    assert again.id == spent.id and again.duplicate and await service.balance(user, "coins") == 20
    with pytest.raises(InsufficientCoins) as refused:
        await service.spend(
            user, 21, reason="x", source_kind="marketplace", source_ref="item:2", idempotency_key="o2"
        )
    assert refused.value.code == "economy.insufficient_coins"
    assert await service.balance(user, "coins") == 20
    refund = await service.refund(spent.id, reason="cancelled", idempotency_key="r1")
    assert refund.delta == 30 and refund.reverses_transaction_id == spent.id and refund.kind == "refund"
    assert (await service.refund(spent.id, reason="cancelled", idempotency_key="r1")).duplicate
    with pytest.raises(Conflict):
        await service.refund(spent.id, reason="twice", idempotency_key="r2")
    with pytest.raises(ValidationFailed):
        await service.spend(
            user, 1, reason="x", source_kind="reward_rule", source_ref="y", idempotency_key="o3"
        )
    assert await service.balance(user, "coins") == 50


async def test_history_is_owner_only_and_paginated(gm: GamHarness, client: AsyncClient) -> None:
    user = gm.people["ursula"]
    for i in range(55):
        await gm.module.rewards.grant_manual(
            gm.p("boss"), user, "xp", 1, reason="seed", idempotency_key=f"h{i}"
        )
    await login(client, "ursula")
    first = (await client.get("/api/v1/me/economy/transactions")).json()
    assert len(first["items"]) == 50 and first["next_cursor"]
    second = (
        await client.get("/api/v1/me/economy/transactions", params={"cursor": first["next_cursor"]})
    ).json()
    assert len(second["items"]) == 5 and second["next_cursor"] is None
    progression = (await client.get("/api/v1/me/progression")).json()
    assert progression["xp"] == 55 and progression["level"] == 1 and progression["coins"] == 0
    await login(client, "ulrich")
    assert (await client.get("/api/v1/me/economy/transactions")).json()["items"] == []
    assert (await client.get(f"/api/v1/admin/economy/transactions?user={user}")).status_code == 403
