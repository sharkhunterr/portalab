"""018 T013 — an AI failure never breaks classic features: provider down/timeout ⇒ ``ai.unavailable`` on
the AI stream only; a mid-turn failure executes nothing sensitive; the turn is still stored; rate and
budget exhaustion answer politely before any provider call; the concurrency cap holds."""

import asyncio
from datetime import date
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select, text

from portalab.capabilities.ai.testkit import call
from portalab.modules.ai.errors import AiRateLimited
from portalab.modules.ai.models import Message, PendingAction, UsageDaily
from tests.integration.ai.conftest import AiHarness, Recorder, make_tool, names, say, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_provider_failure_is_contained(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    conversation = await start(client)
    ai.provider.fail = "unreachable"
    events = await say(client, conversation, "hello?")
    assert names(events) == ["error"] and events[0][1] == {"code": "ai.unavailable", "reason": "unreachable"}
    assert (await client.get("/api/v1/me")).status_code == 200
    detail = (await client.get(f"/api/v1/ai/conversations/{conversation}")).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["blocks"]["error"] == "unreachable"


async def test_mid_turn_failure_executes_nothing_sensitive(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    sensitive = Recorder()
    ai.tools.register(make_tool("demo.wipe", "ai.use", "sensitive", sensitive))
    await login(client, "ursula")
    ai.provider.turns = [[call("demo.wipe", "c1", q="all")]]

    original = ai.provider.chat
    calls = {"n": 0}

    def flaky(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 2:
            ai.provider.fail = "timeout"
        return original(*args, **kwargs)

    ai.provider.chat = flaky  # type: ignore[method-assign]
    events = await say(client, await start(client), "wipe everything")
    assert names(events)[-1] == "error" and "pending_action" in names(events)
    assert sensitive.calls == []  # proposed, never executed
    async with ai.full.database.session() as session:
        statuses = (await session.execute(select(PendingAction.status))).scalars().all()
    assert statuses == ["pending"]


async def test_rate_limit_and_budget(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    conversation = await start(client)
    ai.module.config = type(ai.module.config)(enabled=True, rate_limit_per_minute=2)
    for _ in range(2):
        await say(client, conversation, "hi")
    limited = await client.post(f"/api/v1/ai/conversations/{conversation}/messages", json={"content": "hi"})
    assert limited.status_code == 429 and limited.json()["code"] == "ai.rate_limited"
    ai.module.config = type(ai.module.config)(
        enabled=True, rate_limit_per_minute=50, daily_token_budget_per_user=100
    )
    async with ai.full.database.unit_of_work() as uow:
        await uow.session.execute(
            text("UPDATE ai.usage_daily SET tokens_in = 1000 WHERE user_id = :u"), {"u": people["ursula"]}
        )
    calls_before = len(ai.provider.calls)
    over = await client.post(f"/api/v1/ai/conversations/{conversation}/messages", json={"content": "hi"})
    assert over.status_code == 429 and over.json()["code"] == "ai.budget_exceeded"
    assert len(ai.provider.calls) == calls_before  # refused before any provider call
    async with ai.full.database.session() as session:
        usage = await session.get(UsageDaily, (people["ursula"], ai.clock.now().date()))
        stored = (await session.execute(select(Message.role))).scalars().all()
    assert usage is not None and usage.requests == 2 and isinstance(usage.day, date)
    assert stored.count("user") == 2  # refused messages are not stored


async def test_concurrency_cap(ai: AiHarness, people: dict[str, UUID]) -> None:
    user = people["ursula"]
    governor = ai.module.governor
    async with governor.slot(user), governor.slot(user):
        with pytest.raises(AiRateLimited):
            async with governor.slot(user):
                pass
    async with governor.slot(user):  # released
        await asyncio.sleep(0)
