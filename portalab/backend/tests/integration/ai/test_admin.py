"""018 T030/T031 — admin API behind ``ai.manage``: configuration (secrets write-only), provider test,
usage aggregates without content, MCP allow-list; non-admins are refused."""

from uuid import UUID

import httpx
import pytest

from tests.integration.ai.conftest import AiHarness, say, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_admin_only(ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]) -> None:
    await login(client, "ursula")
    for method, path in (
        ("GET", "/api/v1/admin/ai/config"),
        ("PUT", "/api/v1/admin/ai/config"),
        ("POST", "/api/v1/admin/ai/provider/test"),
        ("GET", "/api/v1/admin/ai/usage"),
        ("GET", "/api/v1/admin/ai/mcp-servers"),
    ):
        response = await client.request(method, path, json={} if method != "GET" else None)
        assert response.status_code == 403, path


def unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("down", request=request)


async def test_config_usage_and_mcp(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    ai.module.mcp.transport = httpx.MockTransport(unreachable)
    await login(client, "ursula")
    await say(client, await start(client), "private words")
    await login(client, "boss")
    updated = await client.put(
        "/api/v1/admin/ai/config",
        json={
            "enabled": True,
            "provider_model": "llama3",
            "provider_secret": "sk-new-key-123456",
            "auto_navigate": True,
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["values"]["provider_model"] == "llama3" and body["values"]["auto_navigate"] is True
    assert body["provider_secret_set"] is True and "sk-new-key-123456" not in updated.text
    assert ai.module.api_key == "sk-new-key-123456"
    assert any(t["name"] == "navigate.suggest" for t in body["tools"])
    tested = (await client.post("/api/v1/admin/ai/provider/test")).json()
    assert tested["ok"] is True
    usage = await client.get("/api/v1/admin/ai/usage")
    assert usage.json()["days"][0]["requests"] == 1 and "private words" not in usage.text
    bad = await client.put(
        "/api/v1/admin/ai/mcp-servers", json={"servers": [{"name": "x", "url": "ftp://nope"}]}
    )
    assert bad.status_code == 422
    saved = await client.put(
        "/api/v1/admin/ai/mcp-servers",
        json={
            "servers": [
                {
                    "name": "mcparr",
                    "url": "http://mcparr.invalid/mcp",
                    "allowlist": [
                        {"tool": "get_status", "permission": "services.read", "sensitivity": "read"}
                    ],
                }
            ],
            "credentials": {"mcparr": "tok-SECRET-1"},
        },
    )
    assert saved.status_code == 200, saved.text
    server = saved.json()[0]
    assert (
        server["credential_set"] is True
        and server["state"] == "unavailable"
        and "tok-SECRET-1" not in saved.text
    )
