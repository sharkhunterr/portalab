"""018 T033 — no secret anywhere: the provider key and MCP credentials never reach prompts, tool results,
streamed events, stored messages, logs, events, audit or admin responses; audit and events carry ids and
hashes, never prompt text."""

import json
import logging
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from portalab.capabilities.ai import ToolResult
from portalab.capabilities.ai.testkit import call
from tests.integration.ai.conftest import AiHarness, Recorder, make_tool, say, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration
KEY = "sk-prov-SECRET-abcdef0123"
MCP = "mcp-token-SECRET-987654"
PROMPT = "my confidential question about payroll"


async def test_no_secret_anywhere(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    ai.module.api_key, ai.module.mcp_tokens = KEY, {"mcparr": MCP}
    leaky = Recorder(
        ToolResult("ok", {"service": "media", "api_key": KEY, "nested": {"password": "hunter22"}})
    )
    ai.tools.register(make_tool("demo.leaky", "ai.use", handler=leaky))
    ai.tools.register(make_tool("demo.purge", "ai.use", "sensitive"))
    ai.provider.turns = [
        [call("demo.leaky", "c1"), call("demo.purge", "c2", q="x")],
        [f"Here: {KEY} and {MCP}"],
    ]
    await login(client, "boss")
    conversation = await start(client)
    events = await say(client, conversation, PROMPT)
    prompts = json.dumps([[m.content for m in messages] for messages, _ in ai.provider.calls])
    assert KEY not in prompts and "hunter22" not in prompts and MCP not in prompts
    streamed = json.dumps([d for _, d in events])
    detail = json.dumps((await client.get(f"/api/v1/ai/conversations/{conversation}")).json())
    admin = json.dumps((await client.get("/api/v1/admin/ai/config")).json())
    assert all(secret not in blob for secret in (KEY, MCP) for blob in (streamed, detail, admin, caplog.text))
    assert json.loads(admin)["provider_secret_set"] is True
    async with ai.full.database.session() as session:
        audit = json.dumps(
            [
                list(r)
                for r in (
                    await session.execute(text("SELECT action, context::text FROM audit.audit_entries"))
                ).all()
            ]
        )
        outbox = json.dumps(
            [
                r[0]
                for r in (await session.execute(text("SELECT metadata::text FROM core.event_outbox"))).all()
            ]
        )
    for blob in (audit, outbox):
        assert KEY not in blob and MCP not in blob and PROMPT not in blob
    assert "params_hash" in audit
