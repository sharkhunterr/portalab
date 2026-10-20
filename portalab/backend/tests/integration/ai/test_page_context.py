"""Issue 171 — the page a message is asked from reaches the model: a conversation started on one page goes
on on another, and « this » means what the page the member is on now shows (only its route and a short
line: « media id=… »)."""

from uuid import UUID

import httpx
import pytest

from tests.integration.ai.conftest import AiHarness, parse_sse, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_each_message_tells_its_page(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    conversation = await start(client, {"route": "/", "title": "Home"})
    first = await client.post(f"/api/v1/ai/conversations/{conversation}/messages", json={"content": "Hello"})
    assert first.status_code == 200 and parse_sse(first.text)
    assert '"/"' in ai.provider.calls[-1][0][0].content  # the page it started on
    second = await client.post(
        f"/api/v1/ai/conversations/{conversation}/messages",
        json={"content": "Why is this leaving?", "context": {"route": "/media/m1", "title": "media id=m1"}},
    )
    assert second.status_code == 200
    system = ai.provider.calls[-1][0][0].content
    assert '"/media/m1"' in system and "media id=m1" in system and "look it up" in system
    assert f'You speak with the member "ursula" (id {people["ursula"]})' in system  # who « me » is
    refused = await client.post(
        f"/api/v1/ai/conversations/{conversation}/messages",
        json={"content": "x", "context": {"route": "/x", "question": "not a page field"}},
    )
    assert refused.status_code == 422
