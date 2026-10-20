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
    assert "decide whether the question is about what this page shows" in system  # else: the page is ignored
    assert "ignore the page entirely" in system
    assert f'You speak with the member "ursula" (id {people["ursula"]})' in system  # who « me » is
    asked = next(m for m in ai.provider.calls[-1][0] if m.content.startswith("Why is this leaving?"))
    assert (
        asked.role == "user"
        and asked.content.startswith("Why is this leaving?")
        and "look it up" in asked.content
    )
    stored = (await client.get(f"/api/v1/ai/conversations/{conversation}")).json()["messages"]
    assert [m["content"] for m in stored if m["role"] == "user"] == [
        "Hello",
        "Why is this leaving?",
    ]  # never stored
    refused = await client.post(
        f"/api/v1/ai/conversations/{conversation}/messages",
        json={"content": "x", "context": {"route": "/x", "question": "not a page field"}},
    )
    assert refused.status_code == 422


async def test_a_real_question_answered_from_thin_air_is_asked_again(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    """Once, an answer made up without looking anything up is dropped and the model asked to look first;
    small talk is answered as it comes."""
    from portalab.capabilities.ai.testkit import call
    from tests.integration.ai.conftest import make_tool

    ai.tools.register(make_tool("docs.search", "ai.use"))
    await login(client, "ursula")
    conversation = await start(client)
    ai.provider.turns = [
        ["You change it in the settings, I think."],
        [call("docs.search", q="avatar")],
        ["See the wiki."],
    ]
    body = (
        await client.post(
            f"/api/v1/ai/conversations/{conversation}/messages",
            json={"content": "How do I change my avatar?"},
        )
    ).text
    events = parse_sse(body)
    shown = "".join(data["text"] for name, data in events if name == "delta")
    assert "I think" not in shown and "See the wiki." in shown  # the made-up answer never reached the member
    assert any(name == "tool_call" for name, _ in events)
    assert "You answered without looking anything up" in ai.provider.calls[1][0][-1].content
    before = len(ai.provider.calls)
    ai.provider.turns = [["Hello!"]]
    await client.post(f"/api/v1/ai/conversations/{conversation}/messages", json={"content": "Bonjour"})
    assert len(ai.provider.calls) == before + 1  # small talk: no second try
