"""018 T016 — action parity: AI tools run the **same domain services** as the human API. A write tool
wrapping ticket creation hits Support's own rule (the assistant only drafts tickets); a confirmed
sensitive action (declaring an incident) emits the same events and audit entries as the human path, with
the AI actor acting for the user — audit carries ids and a parameters hash, never the conversation."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from portalab.capabilities.ai import ToolResult
from portalab.capabilities.ai.testkit import call
from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.events import EventTypeRegistry
from portalab.capabilities.observability import ObservableRegistry
from portalab.capabilities.search import SearchRegistry
from portalab.capabilities.support import TICKETS, TicketRequest
from portalab.core.authz_port import Principal
from portalab.core.blobstore import FileSystemBlobStore
from portalab.modules.support.module import SupportModule
from tests.integration.ai.conftest import AiHarness, make_tool, say, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


@pytest.fixture
async def support(ai: AiHarness, tmp_path: Path) -> SupportModule:
    module = SupportModule(
        ai.full.database,
        ai.full.authz.engine.events,
        ai.full.authz.audit,
        ai.full.identity.capabilities,
        ai.full.authz.engine,
        clock=ai.clock,
        widgets=WidgetRegistry(),
        search=SearchRegistry(),
        event_types=EventTypeRegistry(),
        observables=ObservableRegistry(),
        actions=ActionRegistry(),
        blobs=FileSystemBlobStore(tmp_path / "support"),
    )
    module.register()
    await module.definitions.ensure_baseline()

    async def create_ticket(principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        port = ai.full.identity.capabilities.system_providers(TICKETS)[0].provider
        ref = await port.create(TicketRequest("question", str(params["q"]), "from the assistant"), principal)
        return ToolResult("ok", {"number": ref.number})

    async def declare(principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        view, _ = await module.incidents.create(principal, title=str(params["q"]), severity="minor")
        return ToolResult("ok", {"reference": view.reference})

    ai.tools.register(make_tool("tickets.create", "tickets.create", "write", create_ticket))
    ai.tools.register(make_tool("incidents.declare", "incidents.manage", "sensitive", declare))
    return module


async def test_domain_rules_apply_to_the_assistant(
    ai: AiHarness, support: SupportModule, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    ai.provider.turns = [[call("tickets.create", "c1", q="Printer broken")], ["I could not."]]
    events = await say(client, await start(client), "open a ticket")
    assert [d["state"] for n, d in events if n == "tool_result"] == ["error"]
    tool_message = next(m.content for m in ai.provider.calls[1][0] if m.role == "tool")
    assert "ticket.ai_cannot_submit" in tool_message
    async with ai.full.database.session() as session:
        assert await session.scalar(text("SELECT count(*) FROM support.tickets")) == 0


async def test_confirmed_action_matches_the_human_path(
    ai: AiHarness, support: SupportModule, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    await support.incidents.create(ai.p("boss"), title="Human path", severity="minor")
    await login(client, "boss")
    ai.provider.turns = [[call("incidents.declare", "c1", q="Assistant path")], ["Please confirm."]]
    events = await say(client, await start(client), "declare an incident about the NAS secret plan")
    action = next(d["id"] for n, d in events if n == "pending_action")
    async with ai.full.database.session() as session:
        assert await session.scalar(text("SELECT count(*) FROM support.incidents")) == 1  # not yet
    assert (await client.post(f"/api/v1/ai/actions/{action}/confirm")).json()["status"] == "executed"
    async with ai.full.database.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT actor_channel, actor_id FROM core.event_outbox WHERE type = 'incident.created' "
                    "ORDER BY received_at, seq"
                )
            )
        ).all()
        audits = (
            await session.execute(
                text(
                    "SELECT actor_kind, acting_for, context::text FROM audit.audit_entries "
                    "WHERE action = 'incident.created' ORDER BY seq"
                )
            )
        ).all()
        confirmed = (
            (
                await session.execute(
                    text("SELECT context::text FROM audit.audit_entries WHERE action = 'ai.action_confirmed'")
                )
            )
            .scalars()
            .all()
        )
    boss = people["boss"]
    assert [(r.actor_channel, r.actor_id) for r in rows] == [("user", boss), ("ai", boss)]
    assert [a.actor_kind for a in audits] == ["user", "ai"] and audits[1].acting_for == boss
    assert len(confirmed) == 1 and "params_hash" in confirmed[0] and "NAS secret plan" not in confirmed[0]
