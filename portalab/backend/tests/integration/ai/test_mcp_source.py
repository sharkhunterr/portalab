"""018 T029 — MCP servers (e.g. MCParr) behind the Admin allow-list: only mapped tools appear (with their
portal permission and sensitivity), the portal authorizes before each call, sensitive MCP tools need
confirmation, a server that is down contributes nothing while the assistant keeps working, credentials
come from the secret setting and never reach the model."""

import json
from typing import Any
from uuid import UUID

import httpx
import pytest

from portalab.capabilities.ai import ToolCall
from portalab.capabilities.ai.testkit import call
from tests.integration.ai.conftest import AiHarness, done, say, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration
TOKEN = "mcparr-SECRET-token-42"


class FakeMcp:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.down = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("down", request=request)
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        message = json.loads(request.content)
        method = message["method"]
        if method == "initialize":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": message["id"], "result": {}},
                headers={"mcp-session-id": "s-1"},
            )
        assert request.headers["mcp-session-id"] == "s-1"
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "tools/list":
            tools = [
                {
                    "name": "get_status",
                    "description": "Homelab status",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "restart_container",
                    "description": "Restart",
                    "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}},
                },
                {"name": "dump_secrets", "description": "Everything", "inputSchema": {"type": "object"}},
            ]
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": message["id"], "result": {"tools": tools}}
            )
        self.calls.append(message["params"])
        body = {
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {"content": [{"type": "text", "text": "all green"}]},
        }
        stream = f"event: message\ndata: {json.dumps(body)}\n\n"
        return httpx.Response(200, text=stream, headers={"content-type": "text/event-stream"})


def configure(ai: AiHarness, server: FakeMcp) -> None:
    ai.module.mcp.transport = httpx.MockTransport(server)
    ai.module.mcp_tokens = {"mcparr": TOKEN}
    ai.module.config = type(ai.module.config)(
        enabled=True,
        rate_limit_per_minute=100,
        mcp_servers=[
            {
                "name": "mcparr",
                "url": "http://mcparr.test/mcp",
                "allowlist": [
                    {"tool": "get_status", "permission": "services.read", "sensitivity": "read"},
                    {"tool": "restart_container", "permission": "services.manage", "sensitivity": "write"},
                    {"tool": "unknown_tool", "permission": "services.read", "sensitivity": "read"},
                ],
            }
        ],
    )


async def test_allow_listed_tools_only(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    server = FakeMcp()
    configure(ai, server)
    user = await ai.module.catalog.for_principal(ai.p("ursula"))
    admin = await ai.module.catalog.for_principal(ai.p("boss"))
    assert "mcp.mcparr.get_status" in user and "mcp.mcparr.restart_container" not in user
    assert (
        admin["mcp.mcparr.restart_container"].sensitivity == "sensitive"
    )  # services.manage needs confirmation
    assert not any("dump_secrets" in name or "unknown_tool" in name for name in admin)
    ai.provider.turns = [[call("mcp.mcparr.get_status", "c1")], ["All green [1]."]]
    await login(client, "ursula")
    events = await say(client, await start(client), "homelab status?")
    assert server.calls == [{"name": "get_status", "arguments": {}}]
    assert done(events)["sources"][0]["kind"] == "mcp"
    prompts = json.dumps([[m.content for m in msgs] for msgs, _ in ai.provider.calls])
    assert TOKEN not in prompts and "all green" in prompts


async def test_sensitive_mcp_tool_and_outage(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    server = FakeMcp()
    configure(ai, server)
    ai.provider.turns = [[ToolCall("c1", "mcp.mcparr.restart_container", {"name": "jellyfin"})], ["Confirm?"]]
    await login(client, "boss")
    conversation = await start(client)
    events = await say(client, conversation, "restart jellyfin")
    action = next(d["id"] for n, d in events if n == "pending_action")
    assert server.calls == []
    confirmed = await client.post(f"/api/v1/ai/actions/{action}/confirm")
    assert confirmed.json()["status"] == "executed"
    assert server.calls == [{"name": "restart_container", "arguments": {"name": "jellyfin"}}]
    server.down = True
    await ai.module.mcp.refresh(force=True)
    assert not [t for t in ai.module.catalog.all() if t.name.startswith("mcp.")]
    assert ai.module.mcp.states() == {"mcparr": "unavailable"}
    ai.provider.turns = [["Still here."]]
    assert done(await say(client, conversation, "hello"))["content"] == "Still here."
