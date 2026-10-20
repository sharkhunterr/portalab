"""Issue 171 — the assistant's support tools, run as the member it acts for: their own tickets, one ticket by
its number with its public replies (never the staff's internal notes, never another member's ticket), and a
ticket prepared as a draft the member opens, reads and submits — the assistant itself still cannot submit."""

from uuid import UUID

import httpx
import pytest

from portalab.core.authz_port import Principal
from portalab.core.errors import Forbidden
from portalab.modules.support.ai_tools import SupportAiTools
from portalab.modules.support.tickets.service import TicketRequest
from tests.integration.identity.helpers import login
from tests.integration.support.conftest import SupportHarness


def ai(user: UUID) -> Principal:
    return Principal(channel="ai", acting_for=user)


async def test_my_tickets_one_ticket_and_a_draft(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    tickets = support.module.tickets
    mine = await tickets.create(
        support.p("ursula"), TicketRequest("bug", "Player crashes", "It crashes", {"steps": "Press play"})
    )
    await tickets.comment(support.p("sam"), mine.id, "Can you try another browser?")
    await tickets.comment(support.p("sam"), mine.id, "Probably the codec again", internal=True)
    await tickets.comment(support.p("ursula"), mine.id, "Same in Firefox.")
    tools = {t.name: t for t in SupportAiTools(support.module).tools()}
    assert set(tools) == {"support.my_tickets", "support.ticket", "support.draft_ticket"}
    assert tools["support.draft_ticket"].sensitivity == "write"

    listed = await tools["support.my_tickets"].handler(ai(people["ursula"]), {})
    assert [(t["number"], t["title"], t["state"]) for t in listed.data["tickets"]] == [
        (mine.number, "Player crashes", "open")
    ]
    assert listed.sources[0].url == f"/support/tickets/{mine.id}"
    assert (await tools["support.my_tickets"].handler(ai(people["ursula"]), {"state": "resolved"})).data == {
        "tickets": []
    }

    one = (await tools["support.ticket"].handler(ai(people["ursula"]), {"number": mine.number})).data
    assert one["found"] and one["state"] == "open" and one["fields"] == {"steps": "Press play"}
    assert [r["text"] for r in one["last_replies"]] == ["Can you try another browser?", "Same in Firefox."]
    assert [r["from_requester"] for r in one["last_replies"]] == [False, True]  # no internal note
    other = await tools["support.ticket"].handler(ai(people["ulrich"]), {"number": mine.number})
    assert other.data == {"found": False, "number": mine.number}  # another member's ticket
    assert (await tools["support.ticket"].handler(ai(people["ursula"]), {"number": 99999})).data[
        "found"
    ] is False

    drafted = await tools["support.draft_ticket"].handler(
        ai(people["ursula"]),
        {"title": "Subtitles out of sync", "description": "On every episode of season 2.", "type": "nope"},
    )
    assert drafted.state == "ok" and drafted.data["url"] == f"/support/new?draft={drafted.data['draft']}"
    assert drafted.data["type"] in {t.key for t in await support.module.definitions.types()}
    assert len(await tickets.mine(people["ursula"])) == 1  # nothing sent
    await login(client, "ursula")
    draft = (await client.get(f"/api/v1/tickets/drafts/{drafted.data['draft']}")).json()
    assert draft["payload"]["title"] == "Subtitles out of sync"
    await login(client, "ulrich")
    assert (await client.get(f"/api/v1/tickets/drafts/{drafted.data['draft']}")).status_code == 404
    with pytest.raises(Forbidden):  # the assistant never submits
        await tickets.create(ai(people["ursula"]), TicketRequest("bug", "x", "y", {"steps": "z"}))
