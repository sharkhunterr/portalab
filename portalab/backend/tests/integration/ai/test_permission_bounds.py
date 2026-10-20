"""018 T008 — the assistant offers and runs only what the user may do: the catalog is filtered per
principal (AI channel acting for the user), a hallucinated call to an unpermitted tool is refused at
execution without running it, AI-forbidden tools are absent even for the Admin, and a disabled assistant
answers ``unavailable`` while the classic API keeps working."""

from uuid import UUID

import httpx
import pytest

from portalab.capabilities.ai.testkit import call
from portalab.core.authz_port import Principal
from portalab.modules.ai.tools.catalog import READ_ONLY
from tests.integration.ai.conftest import AiHarness, Recorder, done, make_tool, say, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


def register(ai: AiHarness) -> dict[str, Recorder]:
    handlers = {name: Recorder() for name in ("everyone", "admins", "forbidden", "flagged")}
    ai.tools.register(make_tool("demo.everyone", "ai.use", handler=handlers["everyone"]))
    ai.tools.register(make_tool("demo.admins", "users.manage", handler=handlers["admins"]))
    ai.tools.register(make_tool("demo.forbidden", "ai.manage", handler=handlers["forbidden"]))
    ai.tools.register(make_tool("demo.flagged", "ai.use", "ai_forbidden", handlers["flagged"]))
    return handlers


async def test_catalog_is_filtered_per_principal(ai: AiHarness, people: dict[str, UUID]) -> None:
    register(ai)
    user = await ai.module.catalog.for_principal(ai.p("ursula"))
    admin = await ai.module.catalog.for_principal(ai.p("boss"))
    assert "demo.everyone" in user and "demo.admins" not in user
    assert {"demo.everyone", "demo.admins"} <= set(admin)
    assert not {"demo.forbidden", "demo.flagged"} & set(admin)  # never for the AI, even for the Admin
    readonly = await ai.module.catalog.for_principal(ai.p("ursula"), READ_ONLY)
    assert set(readonly) <= {t for t, tool in user.items() if tool.sensitivity == "read"}
    anonymous_like = Principal(channel="ai", acting_for=None)
    with pytest.raises(ValueError, match="identified user"):
        await ai.module.catalog.for_principal(anonymous_like)


async def test_hallucinated_call_is_refused(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    handlers = register(ai)
    await login(client, "ursula")
    ai.provider.turns = [
        [call("demo.admins", "c1"), call("demo.forbidden", "c2"), call("demo.everyone", "c3", q="x")],
        ["Done."],
    ]
    events = await say(client, await start(client), "do admin things")
    results = {data["name"]: data["state"] for name, data in events if name == "tool_result"}
    assert results == {"demo.admins": "error", "demo.forbidden": "error", "demo.everyone": "ok"}
    assert not handlers["admins"].calls and not handlers["forbidden"].calls
    principal, _ = handlers["everyone"].calls[0]
    assert (
        principal.channel == "ai" and principal.acting_for == people["ursula"] and principal.user_id is None
    )
    offered = {spec.name for spec in ai.provider.calls[0][1]}
    assert "demo__everyone" in offered  # tool names travel in provider-safe form
    assert not {"demo__admins", "demo__forbidden", "demo__flagged"} & offered
    tool_messages = [m.content for m in ai.provider.calls[1][0] if m.role == "tool"]
    assert any("ai.tool_forbidden" in m for m in tool_messages)
    assert "users.manage" not in " ".join(tool_messages)  # refusal reveals nothing about the tool
    assert done(events)["content"] == "Done."


async def test_invalid_parameters_never_run(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    handlers = register(ai)
    await login(client, "ursula")
    ai.provider.turns = [[call("demo.everyone", "c1", q=5, extra=True)], ["ok"]]
    events = await say(client, await start(client), "go")
    assert [d["state"] for n, d in events if n == "tool_result"] == ["error"]
    assert not handlers["everyone"].calls


async def test_disabled_assistant_and_classic_api(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    conversation = await start(client)
    status = (await client.get("/api/v1/ai/status")).json()
    assert status == {
        "available": True,
        "provider_state": "ok",
        "auto_navigate": False,
        "name": "Nova",  # issue 171: its friendly name until the administrators give theirs
        "daily_budget": 50000,
        "used_today": 0,
        "ideas": [],  # issue 174: none set — the window shows the translated defaults
        "recharge": 0,  # issue 173: nothing bought in the shop yet, which sells the assistant's capacities
        "perks": {},
        "shop": True,
    }
    ai.module.config = type(ai.module.config)(enabled=False)
    assert (await client.get("/api/v1/ai/status")).json()["available"] is False
    refused = await client.post(f"/api/v1/ai/conversations/{conversation}/messages", json={"content": "hi"})
    assert refused.status_code == 503 and refused.json()["code"] == "ai.unavailable"
    assert (await client.get("/api/v1/me")).status_code == 200  # classic features unaffected
    assert (await client.get("/api/v1/ai/conversations")).status_code == 200
