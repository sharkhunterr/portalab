"""Spec 032 — a household's economy is pooled: whatever a profile earns (XP, Coins, Contribution) is recorded
once more for its master, a replay never doubles it, the copy rewards nothing again; what a profile spends
is debited from both, refused when the household cannot cover it; a correction is mirrored up to what the
master holds. A profile's master may keep features out of it: their permissions are withheld."""

from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from portalab.capabilities.economy import ECONOMY, InsufficientCoins
from portalab.core.authz_port import Principal
from portalab.modules.gamification.models import LedgerTransaction
from tests.integration.gamification.conftest import GamHarness


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
