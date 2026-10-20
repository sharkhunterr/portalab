"""Issue 173 — the assistant's capacities bought in the shop: a recharge lets a member past their day and is
spent by what goes past it; more tokens a day stop at the administrators' ceiling; the stronger model answers
for those who bought it, the reserved tools are offered to them only; a capacity the portal does not offer
cannot be granted, and a revoke withdraws it."""

from dataclasses import replace
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from portalab.capabilities.ai import PERKS
from tests.integration.ai.conftest import AiHarness, make_tool, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_capacities_bought(ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]) -> None:
    ai.tools.register(make_tool("docs.search", "ai.use"))
    ai.tools.register(make_tool("docs.deep", "ai.use"))
    ai.module.config = replace(
        ai.module.config,
        daily_token_budget_per_user=50,
        premium_model="big-model",
        premium_tools=["docs.deep"],
        max_daily_tokens_per_user=80,
        max_recharge_tokens=100_000,
    )
    perks = ai.full.identity.capabilities.system_providers(PERKS)[0].provider
    ursula = people["ursula"]

    await login(client, "ursula")
    conversation = await start(client)
    ai.provider.turns = [["Hello there."]]
    sent = await client.post(f"/api/v1/ai/conversations/{conversation}/messages", json={"content": "hi"})
    assert sent.status_code == 200
    refused = await client.post(f"/api/v1/ai/conversations/{conversation}/messages", json={"content": "hi"})
    assert refused.status_code == 429 and refused.json()["code"] == "ai.budget_exceeded"
    assert "docs.deep" not in {t["name"] for t in (await client.get("/api/v1/ai/tools")).json()}

    # what the shop hands over, per purchase (idempotent); one the portal does not offer is refused
    assert await perks.grant(ursula, "recharge", 60_000, 0, "marketplace:r1")
    assert await perks.grant(ursula, "recharge", 60_000, 0, "marketplace:r1")  # the same purchase again
    assert await perks.grant(ursula, "daily_tokens", 1_000, 168, "marketplace:d1")
    assert await perks.grant(ursula, "model", 0, 24, "marketplace:m1")
    assert await perks.grant(ursula, "tools", 0, 0, "marketplace:t1")
    assert not await perks.grant(ursula, "wishes", 3, 0, "marketplace:x1")
    async with ai.full.database.session() as session:  # issue 181: one per grant, for the achievements
        gained = (
            await session.execute(
                text("SELECT subject_id FROM core.event_outbox WHERE type = 'ai.capacity_gained'")
            )
        ).scalars()
        assert list(gained) == [str(ursula)] * 4
    status = (await client.get("/api/v1/ai/status")).json()
    assert status["daily_budget"] == 80  # 50 + 1000, to the administrators' ceiling
    assert status["recharge"] == 60_000 and {"model", "tools", "daily_tokens"} <= set(status["perks"])
    assert status["perks"]["tools"] == "forever"
    assert "docs.deep" in {t["name"] for t in (await client.get("/api/v1/ai/tools")).json()}

    ai.provider.turns = [["With the big one."]]
    again = await client.post(f"/api/v1/ai/conversations/{conversation}/messages", json={"content": "hi"})
    assert again.status_code == 200  # past the day, on the recharge
    assert "docs__deep" in {t.name for t in ai.provider.calls[-1][1]}
    left = (await client.get("/api/v1/ai/status")).json()["recharge"]
    assert 0 < left < 60_000  # what went past the day was spent from it

    await login(client, "ulrich")  # the others have none of it
    assert "docs.deep" not in {t["name"] for t in (await client.get("/api/v1/ai/tools")).json()}
    assert (await client.get("/api/v1/ai/status")).json()["daily_budget"] == 50

    await login(client, "boss")
    models = (await client.get("/api/v1/admin/ai/dashboard")).json()["models"]
    assert {m["model"] for m in models} >= {"big-model"}

    await perks.revoke("marketplace:m1")  # refunded or revoked in the shop: withdrawn
    ai.module.config = replace(ai.module.config, perks_offered=["recharge"])  # no longer sold: no effect
    assert set((await perks.upgrade(ursula)).until or {}) == set()
    assert not await perks.grant(ursula, "model", 0, 24, "marketplace:m2")
