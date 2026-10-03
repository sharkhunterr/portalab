"""018 T023 — conversations are owner-only (another user — the Admin included — gets 404 for read,
delete and posting); statistics go through 017 with the AI principal acting for the user (cohort rules
apply there); erasure removes conversations, pending actions and usage; export goes to the owner only."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select

from portalab.capabilities.ai.testkit import call
from portalab.capabilities.statistics import PROVIDER, CatalogEntry, StatResult
from portalab.core.authz_port import Principal
from portalab.modules.ai.models import Conversation, Message, UsageDaily
from portalab.modules.ai.participant import AiParticipant
from tests.integration.ai.conftest import AiHarness, say, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


class FakeStatistics:
    def __init__(self) -> None:
        self.viewers: list[Principal] = []

    async def get(self, stat_key: str, *, viewer: Principal, **_: Any) -> StatResult:
        self.viewers.append(viewer)
        return StatResult(stat_key, "insufficient_data")

    async def catalog(self, viewer: Principal) -> Sequence[CatalogEntry]:
        self.viewers.append(viewer)
        return []


async def test_conversations_are_owner_only(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    conversation = await start(client, {"route": "/services"})
    await say(client, conversation, "my private question")
    for other in ("ulrich", "boss"):
        await login(client, other)
        assert (await client.get(f"/api/v1/ai/conversations/{conversation}")).status_code == 404
        assert (await client.get("/api/v1/ai/conversations")).json() == []
        posted = await client.post(f"/api/v1/ai/conversations/{conversation}/messages", json={"content": "x"})
        assert posted.status_code == 404
        assert (await client.delete(f"/api/v1/ai/conversations/{conversation}")).status_code == 404
    await login(client, "ursula")
    mine = (await client.get("/api/v1/ai/conversations")).json()
    assert [c["id"] for c in mine] == [conversation] and mine[0]["context"] == {"route": "/services"}
    assert mine[0]["title"] == "my private question"
    assert (await client.delete(f"/api/v1/ai/conversations/{conversation}")).status_code == 204
    async with ai.full.database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Message)) == 0


async def test_statistics_run_as_the_user(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    stats = FakeStatistics()
    ai.full.identity.capabilities.provide(PROVIDER, stats, instance_ref="t", owner="module:statistics")
    ai.provider.turns = [[call("statistics.get", "c1", key="media.plays", days=7)], ["Not enough data."]]
    await login(client, "ursula")
    events = await say(client, await start(client), "how many plays?")
    assert [d["state"] for n, d in events if n == "tool_result"] == ["unavailable"]
    assert [(v.channel, v.acting_for) for v in stats.viewers] == [("ai", people["ursula"])]


async def test_erasure_and_export(ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]) -> None:
    await login(client, "ursula")
    await say(client, await start(client), "remember this")
    await login(client, "ulrich")
    await say(client, await start(client), "ulrich's question")
    participant = AiParticipant(ai.full.database)
    exported = await participant.export(people["ursula"])
    assert len(exported) == 1 and "ulrich" not in str(exported[0].data)
    await participant.erase(people["ursula"], "final")
    await participant.erase(people["ursula"], "final")  # idempotent
    async with ai.full.database.session() as session:
        owners = (await session.execute(select(Conversation.user_id))).scalars().all()
        usage = (await session.execute(select(UsageDaily.user_id))).scalars().all()
    assert owners == [people["ulrich"]] and usage == [people["ulrich"]]
