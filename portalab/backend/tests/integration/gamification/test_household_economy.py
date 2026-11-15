"""Spec 032 — a household's economy is pooled: whatever a profile earns (XP, Coins, Contribution) is recorded
once more for its master, a replay never doubles it, the copy rewards nothing again; what a profile spends
is debited from both, refused when the household cannot cover it; a correction is mirrored up to what the
master holds. A profile's master may keep features out of it: their permissions are withheld."""

from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from portalab.capabilities.economy import ECONOMY, InsufficientCoins
from portalab.core.authz_port import Principal
from portalab.modules.gamification.models import LedgerTransaction
from tests.integration.gamification.conftest import GamHarness
from tests.integration.identity.helpers import login


def households(app: FastAPI) -> Any:
    """032: the household module's service (the households are no longer identity's)."""
    return app.state.household_module.service


pytestmark = pytest.mark.integration


async def _child(gm: GamHarness, app: FastAPI, owner: UUID, kind: str = "child") -> UUID:
    created = await households(app).create(
        Principal(user_id=owner), display_name="Léa", kind=kind, color=None, pin=None
    )
    return UUID(str(created["id"]))


async def test_a_profile_earns_for_its_household(gm: GamHarness, app: FastAPI) -> None:
    owner = gm.people["ursula"]
    lea = await _child(gm, app, owner)
    boss = gm.p("boss")
    for value, amount in (("xp", 40), ("coins", 15), ("contribution", 3)):
        await gm.module.rewards.grant_manual(
            boss, lea, value, amount, reason="quest", idempotency_key=f"q-{value}"
        )
        await gm.module.rewards.grant_manual(
            boss, lea, value, amount, reason="quest", idempotency_key=f"q-{value}"
        )
    for value, amount in (("xp", 40), ("coins", 15), ("contribution", 3)):
        assert await gm.balance(lea, value) == amount
        assert await gm.balance(owner, value) == amount  # once, whatever the replays
    async with gm.database.session() as session:
        copies = await session.scalar(
            select(func.count()).select_from(LedgerTransaction).where(LedgerTransaction.profile_id == lea)
        )
    assert copies == 3

    # the master's own earnings stay its own
    await gm.module.rewards.grant_manual(boss, owner, "coins", 100, reason="own", idempotency_key="own")
    assert await gm.balance(lea, "coins") == 15 and await gm.balance(owner, "coins") == 115


async def test_a_master_chooses_a_common_pot_or_dispatched_profiles(
    gm: GamHarness, app: FastAPI, client: httpx.AsyncClient
) -> None:
    """Issue 443: dispatched, a profile keeps its own XP, Coins, contribution and boosters (its own wallet);
    back to a common pot, what it holds is duplicated on its master once (a replay changes nothing);
    dispatched again, the master gives it back. Profiles stay out of the community in a pot only."""
    owner = gm.people["ursula"]
    lea = await _child(gm, app, owner)
    boss = gm.p("boss")
    service = households(app)
    assert await service.economy_of(lea) == "pot" and lea in await service.hidden()

    await login(client, "ursula")
    assert (await client.put("/api/v1/household/economy", json={"economy": "dispatch"})).status_code == 204
    assert (await client.get("/api/v1/household")).json()["economy"] == "dispatch"
    assert lea not in await service.hidden() and lea in await service.anonymous()  # a child: anonymous
    await service.change(Principal(user_id=owner), lea, community_visible=True)
    assert lea not in await service.anonymous()  # public in the community
    for value, amount in (("xp", 40), ("coins", 15), ("contribution", 3)):
        await gm.module.rewards.grant_manual(
            boss, lea, value, amount, reason="quest", idempotency_key=f"d-{value}"
        )
    assert [await gm.balance(lea, v) for v in ("xp", "coins", "contribution")] == [40, 15, 3]
    assert [await gm.balance(owner, v) for v in ("xp", "coins", "contribution")] == [0, 0, 0]
    economy = gm.ev.full.identity.capabilities.system_providers(ECONOMY)[0].provider
    await economy.spend(
        lea, 5, reason="badge", source_kind="marketplace", source_ref="i:1", idempotency_key="sp"
    )
    assert await gm.balance(lea, "coins") == 10 and await gm.balance(owner, "coins") == 0  # its own wallet

    assert (await client.put("/api/v1/household/economy", json={"economy": "pot"})).status_code == 204
    assert [await gm.balance(owner, v) for v in ("xp", "coins", "contribution")] == [
        40,
        10,
        3,
    ]  # the pot rebuilt
    await service.set_economy(Principal(user_id=owner), "pot")  # the same again: nothing moves
    assert await gm.balance(owner, "xp") == 40 and lea in await service.hidden()
    await gm.module.rewards.grant_manual(boss, lea, "xp", 10, reason="quest", idempotency_key="p-xp")
    assert await gm.balance(owner, "xp") == 50  # copied as it comes

    await client.put("/api/v1/household/economy", json={"economy": "dispatch"})
    assert [await gm.balance(owner, v) for v in ("xp", "coins", "contribution")] == [0, 0, 0]  # given back
    assert [await gm.balance(lea, v) for v in ("xp", "coins", "contribution")] == [50, 10, 3]

    assert (await client.post("/api/v1/household/switch", json={"user_id": str(lea)})).status_code == 200
    refused = await client.put("/api/v1/household/economy", json={"economy": "pot"})
    assert refused.status_code == 403  # its master only


async def test_a_profile_spends_the_household_wallet(gm: GamHarness, app: FastAPI) -> None:
    owner = gm.people["ursula"]
    lea = await _child(gm, app, owner)
    service = gm.ev.full.identity.capabilities.system_providers(ECONOMY)[0].provider
    await gm.module.rewards.grant_manual(
        gm.p("boss"), lea, "coins", 30, reason="seed", idempotency_key="seed"
    )
    await service.spend(
        lea, 10, reason="poster", source_kind="marketplace", source_ref="i:1", idempotency_key="s1"
    )
    assert await gm.balance(lea, "coins") == 20 and await gm.balance(owner, "coins") == 20

    # the master spent the household's money: the profile cannot spend what is no longer there
    await service.spend(
        owner, 15, reason="theme", source_kind="marketplace", source_ref="i:2", idempotency_key="s2"
    )
    with pytest.raises(InsufficientCoins):
        await service.spend(
            lea, 10, reason="badge", source_kind="marketplace", source_ref="i:3", idempotency_key="s3"
        )
    assert await gm.balance(lea, "coins") == 20 and await gm.balance(owner, "coins") == 5


async def test_a_master_keeps_features_out_of_a_profile(gm: GamHarness, app: FastAPI) -> None:
    owner = gm.people["ursula"]
    lea = await _child(gm, app, owner)
    tom = await _child(gm, app, owner, kind="standard")
    engine = gm.ev.full.authz.engine
    assert await engine.is_allowed(Principal(user_id=owner), "ai.use")
    assert await engine.is_allowed(Principal(user_id=tom, profile_of=owner), "ai.use")
    assert not await engine.is_allowed(Principal(user_id=lea, profile_of=owner), "ai.use")
    assert "ai.use" not in await engine.visible(
        Principal(user_id=lea, profile_of=owner), ["ai.use", "news.read"]
    )
    assert "news.read" in await engine.effective_permissions(Principal(user_id=lea, profile_of=owner))
