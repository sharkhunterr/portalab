"""016 T033/T039 — the diagnosis flow with a fake AI executor: real data (user, service state, incidents,
wiki pages the user may read and the assistant may use) vs AI interpretation, run as the requesting user;
the result is a draft — never a ticket — and submitting it is an explicit user action; without or on
failure of the executor the diagnosis answers 503 while manual creation works; the 019 action types
``ticket.create`` / ``incident.create`` run as the author under the same rules; AI cannot submit."""

import json
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from portalab.capabilities.content import KNOWLEDGE, KnowledgeHit
from portalab.capabilities.support import DIAGNOSIS, DiagnosisAnalysis, DiagnosisFacts, TicketRequest
from portalab.core.authz_port import Principal
from tests.authz_fixtures import automation
from tests.integration.identity.helpers import login
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration


class Executor:
    def __init__(self) -> None:
        self.calls: list[tuple[DiagnosisFacts, Principal]] = []
        self.fail = False

    async def analyze(self, facts: DiagnosisFacts, principal: Principal) -> DiagnosisAnalysis:
        if self.fail:
            raise RuntimeError("model down")
        self.calls.append((facts, principal))
        return DiagnosisAnalysis(
            summary="The media server looks overloaded.",
            proposed_solution="Wait a few minutes.",
            suggested_title="Media is slow",
            suggested_type="service_issue",
        )


class Wiki:
    async def search(self, text, principal, *, limit=5, for_ai=False):  # type: ignore[no-untyped-def]
        assert for_ai is True
        return [KnowledgeHit("portalab://wiki/9", "Slow media", "Check the load", "/wiki/slow-media")]


def events(raw: str) -> list[tuple[str, dict]]:
    out = []
    for block in raw.strip().split("\n\n"):
        name = block.split("\n")[0].removeprefix("event: ")
        data = json.loads(block.split("\n")[1].removeprefix("data: "))
        out.append((name, data))
    return out


async def test_diagnosis(client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]) -> None:
    await login(client, "ursula")
    body = {"problem": "Media playback stutters since this morning", "service_id": "s1"}
    unavailable = await client.post("/api/v1/diagnosis/runs", json=body)
    assert unavailable.status_code == 503 and unavailable.json()["code"] == "diagnosis.unavailable"
    manual = await client.post(
        "/api/v1/tickets", json={"type_key": "question", "title": "Still works manually"}
    )
    assert manual.status_code == 201
    executor = Executor()
    caps = support.full.identity.capabilities
    caps.provide(DIAGNOSIS, executor, instance_ref="ai", owner="test")
    caps.provide(KNOWLEDGE, Wiki(), instance_ref="wiki", owner="test")
    streamed = events((await client.post("/api/v1/diagnosis/runs", json=body)).text)
    steps = [d for name, d in streamed if name == "step"]
    assert [(s["name"], s["kind"]) for s in steps] == [
        ("identify_user", "real"),
        ("service_state", "real"),
        ("open_incidents", "real"),
        ("search_wiki", "real"),
        ("analyze", "ai"),
        ("propose", "ai"),
        ("prefill_ticket_draft", "real"),
    ]
    done = streamed[-1][1]
    assert done["outcome"] == "ticket_prefilled" and done["draft"]
    facts, principal = executor.calls[0]
    assert principal.user_id == people["ursula"] and facts.wiki[0]["title"] == "Slow media"
    async with support.full.database.session() as session:
        before = (await session.execute(text("SELECT count(*) FROM support.tickets"))).scalar_one()
    assert before == 1  # the draft is not a ticket
    draft = (await client.get(f"/api/v1/tickets/drafts/{done['draft']}")).json()
    assert draft["payload"]["title"] == "Media is slow"
    await login(client, "ulrich")
    assert (await client.get(f"/api/v1/tickets/drafts/{done['draft']}")).status_code == 404  # owner only
    await login(client, "ursula")
    submitted = await client.post(
        "/api/v1/tickets",
        json={
            **{k: draft["payload"][k] for k in ("type_key", "title", "description")},
            "draft_id": done["draft"],
            "service_id": "s1",
        },
    )
    assert submitted.status_code == 201 and submitted.json()["source"] == "ai_diagnosis"
    run = (await client.get(f"/api/v1/diagnosis/runs/{done['run']}")).json()
    assert run["outcome"] == "ticket_prefilled" and len(run["steps"]) == 7
    executor.fail = True
    failed = events((await client.post("/api/v1/diagnosis/runs", json=body)).text)
    assert failed[-1][0] == "error" and failed[-1][1]["code"] == "diagnosis.unavailable"


async def test_automation_actions(support: SupportHarness, people: dict[str, UUID]) -> None:
    ticket_action = support.actions.get("ticket.create")
    incident_action = support.actions.get("incident.create")
    assert ticket_action is not None and incident_action is not None
    made = await ticket_action.run({"type": "question", "title": "From a rule"}, automation(people["ursula"]))
    view = await support.module.tickets.view(UUID(made["ticket"]), support.p("ursula"))
    assert view.ticket.source == "automation" and view.ticket.requester_id == people["ursula"]
    with pytest.raises(Exception):  # noqa: B017 — the author lacks incidents.manage
        await incident_action.run({"title": "x", "dedup_key": "r1"}, automation(people["ursula"]))
    first = await incident_action.run(
        {"title": "Disk full", "dedup_key": "rule-7"}, automation(people["sam"])
    )
    second = await incident_action.run(
        {"title": "Disk full", "dedup_key": "rule-7"}, automation(people["sam"])
    )
    assert first["incident"] == second["incident"] and second["created"] is False
    with pytest.raises(Exception):  # noqa: B017 — the AI only prepares drafts
        await support.module.tickets.create(
            Principal(channel="ai", acting_for=people["ursula"]), TicketRequest("question", "x", "")
        )
