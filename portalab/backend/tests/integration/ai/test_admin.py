"""018 T030/T031 — admin API behind ``ai.manage``: configuration (secrets write-only), provider test,
usage aggregates without content, MCP allow-list; non-admins are refused."""

from datetime import UTC, datetime
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
        ("GET", "/api/v1/admin/ai/servers"),
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


class FakeOllama:
    """A model server as a connected service hands it (issue 169)."""

    def __init__(self, models: list[object] | None = None, *, down: bool = False) -> None:
        self._models = models or []
        self.down = down

    def endpoint(self) -> str:
        return "http://ollama.lan:11434/v1"

    async def models(self) -> list[object]:
        if self.down:
            raise ConnectionError("unreachable")
        return self._models


async def test_model_servers(ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]) -> None:
    """Issue 169: the model servers of the connected services, their models and what is in memory; one
    that does not answer is listed as unavailable — the assistant's settings choose from them."""
    from portalab.capabilities.ai import MODELS, MODELS_SPEC, ModelInfo
    from portalab.capabilities.results import Available

    capabilities = ai.full.identity.capabilities
    try:
        capabilities.spec(MODELS)
    except Exception:
        capabilities.declare(MODELS_SPEC)
    qwen = ModelInfo("qwen3:8b", family="qwen3", loaded=True, vram_bytes=6_000_000_000, tools=True)
    embed = ModelInfo("nomic-embed-text:latest", embedding=True)
    wrapped = FakeOllama()
    wrapped.models = lambda: _available(Available([qwen, embed], as_of=datetime.now(UTC)))  # type: ignore[method-assign]
    capabilities.provide(MODELS, wrapped, instance_ref="s1", metadata={"service_id": "s1", "name": "PC-IA"})
    capabilities.provide(MODELS, FakeOllama(down=True), instance_ref="s2", metadata={"name": "Tower"})
    await login(client, "boss")
    servers = {s["name"]: s for s in (await client.get("/api/v1/admin/ai/servers")).json()}
    assert servers["PC-IA"]["state"] == "ok" and servers["PC-IA"]["endpoint"] == "http://ollama.lan:11434/v1"
    assert [(m["name"], m["loaded"], m["tools"], m["embedding"]) for m in servers["PC-IA"]["models"]] == [
        ("qwen3:8b", True, True, False),
        ("nomic-embed-text:latest", False, None, True),
    ]
    assert servers["Tower"]["state"] == "unavailable" and servers["Tower"]["models"] == []


async def _available(value: object) -> object:
    return value


async def test_the_assistants_name(ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]) -> None:
    """Issue 171: the administrators name the assistant; the members' window shows it."""
    await login(client, "boss")
    saved = await client.put(
        "/api/v1/admin/ai/config",
        json={
            "assistant_name": "Xeno",
            "assistant_fallback": "send them to the FAQ",
            "assistant_ideas": ["Mes demandes en cours ?", "Quoi de neuf ?"],  # issue 174
        },
    )
    assert saved.status_code == 200 and saved.json()["values"]["assistant_name"] == "Xeno"
    await login(client, "ursula")
    status = (await client.get("/api/v1/ai/status")).json()
    assert status["name"] == "Xeno" and status["ideas"] == ["Mes demandes en cours ?", "Quoi de neuf ?"]
