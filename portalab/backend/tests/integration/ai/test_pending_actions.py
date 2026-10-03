"""018 T015 — sensitive actions: a pending action (no execution) with a tool-generated summary; confirmed
in time by its owner it runs once (idempotent) through the confirmation service; decline / expiry ⇒ never
runs; tampered parameters are refused; only the owner, from a user session, can confirm — never the AI;
permissions that require confirmation make a tool sensitive; AI-forbidden tools stay unavailable."""

from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select, text

from portalab.capabilities.ai.testkit import call
from portalab.core.authz_port import Principal
from portalab.core.errors import Forbidden
from portalab.modules.ai.models import PendingAction
from tests.integration.ai.conftest import AiHarness, Recorder, done, make_tool, say, start
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def propose(ai: AiHarness, client: httpx.AsyncClient, recorder: Recorder) -> str:
    ai.tools.register(make_tool("demo.purge", "ai.use", "sensitive", recorder))
    ai.provider.turns = [[call("demo.purge", "c1", q="old")], ["I proposed it; please confirm."]]
    events = await say(client, await start(client), "purge old things")
    pending = [data for name, data in events if name == "pending_action"]
    assert len(pending) == 1 and pending[0]["summary"] == "Run demo.purge with [('q', 'old')]"
    assert done(events)["pending_actions"] == [pending[0]["id"]]
    assert recorder.calls == []
    return str(pending[0]["id"])


async def test_confirm_runs_once(ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]) -> None:
    recorder = Recorder()
    await login(client, "ursula")
    action = await propose(ai, client, recorder)
    shown = (await client.get(f"/api/v1/ai/actions/{action}")).json()
    assert shown["status"] == "pending" and shown["tool"] == "demo.purge"
    confirmed = await client.post(f"/api/v1/ai/actions/{action}/confirm")
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "executed"
    again = await client.post(f"/api/v1/ai/actions/{action}/confirm")
    assert again.json()["status"] == "executed"
    assert len(recorder.calls) == 1
    principal, params = recorder.calls[0]
    assert principal.channel == "ai" and principal.acting_for == people["ursula"] and params == {"q": "old"}
    async with ai.full.database.session() as session:
        events = (
            (await session.execute(text("SELECT type FROM core.event_outbox WHERE type LIKE 'ai.action_%'")))
            .scalars()
            .all()
        )
        audits = (
            await session.execute(
                text("SELECT action, context::text FROM audit.audit_entries WHERE action LIKE 'ai.action_%'")
            )
        ).all()
        consumed = await session.scalar(
            text("SELECT count(*) FROM authz.confirmations WHERE consumed_at IS NOT NULL")
        )
    assert events == ["ai.action_confirmed"]
    assert {a for a, _ in audits} == {"ai.action_proposed", "ai.action_confirmed"}
    assert all("params_hash" in context and "purge old things" not in context for _, context in audits)
    assert consumed == 1


async def test_only_the_owner_from_a_user_session(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    recorder = Recorder()
    await login(client, "ursula")
    action = await propose(ai, client, recorder)
    with pytest.raises(Forbidden):
        await ai.module.pending.confirm(Principal(channel="ai", acting_for=people["ursula"]), UUID(action))
    await login(client, "ulrich")
    assert (await client.get(f"/api/v1/ai/actions/{action}")).status_code == 404
    assert (await client.post(f"/api/v1/ai/actions/{action}/confirm")).status_code == 404
    await login(client, "boss")
    assert (await client.post(f"/api/v1/ai/actions/{action}/confirm")).status_code == 404
    assert recorder.calls == []


async def test_decline_expiry_and_tamper(
    ai: AiHarness, client: httpx.AsyncClient, people: dict[str, UUID]
) -> None:
    recorder = Recorder()
    await login(client, "ursula")
    declined = await propose(ai, client, recorder)
    assert (await client.post(f"/api/v1/ai/actions/{declined}/decline")).json()["status"] == "declined"
    refused = await client.post(f"/api/v1/ai/actions/{declined}/confirm")
    assert refused.status_code == 409 and refused.json()["code"] == "ai.action_expired"

    expired = await propose(ai, client, recorder)
    ai.clock.advance(timedelta(minutes=11))
    assert (await client.get(f"/api/v1/ai/actions/{expired}")).json()["status"] == "expired"
    late = await client.post(f"/api/v1/ai/actions/{expired}/confirm")
    assert late.status_code == 409 and late.json()["code"] == "ai.action_expired"
    assert await ai.module.pending.expire() == 1

    tampered = await propose(ai, client, recorder)
    async with ai.full.database.unit_of_work() as uow:
        await uow.session.execute(
            text('UPDATE ai.pending_actions SET params = \'{"q": "everything"}\' WHERE id = :id'),
            {"id": tampered},
        )
    bad = await client.post(f"/api/v1/ai/actions/{tampered}/confirm")
    assert bad.status_code == 409
    assert recorder.calls == []
    async with ai.full.database.session() as session:
        statuses = sorted((await session.execute(select(PendingAction.status))).scalars().all())
    assert statuses == ["declined", "expired", "pending"]


async def test_sensitivity_follows_the_permission_registry(ai: AiHarness, people: dict[str, UUID]) -> None:
    ai.tools.register(make_tool("demo.delete_news", "news.delete", "write"))
    ai.tools.register(make_tool("demo.transfer", "users.admin.transfer", "sensitive"))
    tools = {t.name: t.sensitivity for t in ai.module.catalog.all()}
    assert tools["demo.delete_news"] == "sensitive"  # news.delete requires confirmation (003)
    assert tools["demo.transfer"] == "ai_forbidden"
    offered = await ai.module.catalog.for_principal(ai.p("boss"))
    assert "demo.transfer" not in offered and offered["demo.delete_news"].sensitivity == "sensitive"
