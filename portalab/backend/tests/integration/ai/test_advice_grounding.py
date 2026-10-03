"""018 T026 — advice is grounded: real data cited with its class and ``as_of``; a citation to a source
not retrieved is dropped; advice citing nothing is labelled interpretation; degraded tool results come
with caveats."""

from collections.abc import Sequence
from datetime import timedelta
from uuid import UUID

import httpx
import pytest

from portalab.capabilities.ai.testkit import call
from portalab.capabilities.health import SERVICE_DIRECTORY, SERVICE_STATE, ServiceInfo, ServiceStateView
from tests.integration.ai.conftest import AiHarness, done, say, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


class States:
    def __init__(self, ai: AiHarness) -> None:
        self.ai = ai

    async def get(self, service_id: str) -> ServiceStateView | None:
        return None

    async def all(self) -> list[ServiceStateView]:
        now = self.ai.clock.now()
        return [ServiceStateView("s1", "unavailable", now - timedelta(hours=1), now, 0.5, now)]


class Directory:
    async def services(self) -> Sequence[ServiceInfo]:
        return [ServiceInfo(id="s1", name="Media", connector="jellyfin", state="enabled")]

    async def service(self, service_id: str) -> ServiceInfo | None:
        return None


async def test_grounded_and_interpreted(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    capabilities = ai.full.identity.capabilities
    capabilities.provide(SERVICE_STATE, States(ai), instance_ref="t", owner="module:health")
    capabilities.provide(SERVICE_DIRECTORY, Directory(), instance_ref="t", owner="module:connectors")
    ai.provider.turns = [
        [call("services.status", "c1", service="media")],
        ["Media is down [1]; the wiki says to restart it [4]."],
        ["You could try restarting your player."],
    ]
    await login(client, "ursula")
    conversation = await start(client)
    events = await say(client, conversation, "is media up?")
    sources = [d for n, d in events if n == "source"]
    assert sources[0]["class"] == "real" and sources[0]["as_of"] and sources[0]["url"] == "/services/s1"
    answer = done(events)
    assert answer["content"] == "Media is down [1]; the wiki says to restart it ."
    assert [s["n"] for s in answer["sources"]] == [1] and answer["interpretation"] is False
    advice = done(await say(client, conversation, "what should I do?"))
    assert advice["sources"] == [] and advice["interpretation"] is True
    ai.provider.turns = [[call("wiki.search", "c1", query="restart")], ["No docs."]]
    caveated = done(await say(client, conversation, "any docs?"))
    assert caveated["caveats"] == [{"tool": "wiki.search", "state": "unavailable"}]
