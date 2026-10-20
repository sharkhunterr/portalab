"""Issue 171 — the assistant's support tools, run as the member it acts for: their own tickets, one ticket by
its number or id with its public replies (never the staff's internal notes, never another member's ticket),
and a ticket the member confirms in Portalab, opened in their name — the assistant alone still cannot."""

from uuid import UUID

import httpx
import pytest

from portalab.core.authz_port import Principal
from portalab.core.errors import Forbidden
from portalab.modules.support.ai_tools import SupportAiTools
from portalab.modules.support.tickets.service import TicketRequest
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
    assert set(tools) == {
        "support.my_tickets",
        "support.ticket",
        "support.create_ticket",
        "incidents.current",
    }
    create = tools["support.create_ticket"]
    assert create.sensitivity == "sensitive"  # never inline: the member confirms its exact content

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
    by_id = await tools["support.ticket"].handler(ai(people["ursula"]), {"id": str(mine.id)})
    assert by_id.data["number"] == mine.number  # the page the member is on names it
    other = await tools["support.ticket"].handler(ai(people["ulrich"]), {"number": mine.number})
    assert other.data == {"found": False, "number": mine.number}  # another member's ticket
    assert (await tools["support.ticket"].handler(ai(people["ursula"]), {"number": 99999})).data[
        "found"
    ] is False

    content = {
        "title": "Subtitles out of sync",
        "description": "On every episode of season 2.",
        "type": "nope",
    }
    assert "Subtitles out of sync" in create.summarize(content)  # what the confirmation card shows
    opened = await create.handler(ai(people["ursula"]), content)  # run by the confirmation
    assert opened.state == "ok" and opened.data["created"] and opened.sources[0].url.startswith("/support/")
    theirs = await tickets.mine(people["ursula"])
    new = next(t for t in theirs if t.title == "Subtitles out of sync")
    assert len(theirs) == 2 and new.source == "ai_diagnosis" and new.number == opened.data["number"]
    lacking = await create.handler(ai(people["ursula"]), {**content, "type": "bug"})  # « bug » asks for steps
    assert lacking.state == "error" and lacking.data["missing"] == ["steps"]
    with pytest.raises(Forbidden):  # the assistant never submits
        await tickets.create(ai(people["ursula"]), TicketRequest("bug", "x", "y", {"steps": "z"}))


async def test_incidents_in_progress_and_lately_resolved(
    support: SupportHarness, people: dict[str, UUID]
) -> None:
    """Issue 171: what is wrong right now — beyond the probes, the incidents the support declared."""
    incidents = support.module.incidents
    outage, _ = await incidents.create(
        support.p("sam"),
        title="Panne générale",
        severity="critical",
        summary="Ralentissement",
        message="On it.",
    )
    [tool] = [
        t
        for t in SupportAiTools(support.module, support.module.clock).tools()
        if t.name == "incidents.current"
    ]
    answer = await tool.handler(ai(people["ursula"]), {})
    [current] = answer.data["in_progress"]
    assert (current["reference"], current["title"], current["severity"]) == (
        outage.reference,
        "Panne générale",
        "critical",
    )
    assert current["services"] == ["the whole portal"] and current["summary"] == "Ralentissement"
    assert answer.data["summary"].startswith("1 incident(s) in progress.")
    assert answer.sources[0].url == f"/incidents/{outage.id}"
    slow, _ = await incidents.create(
        support.p("sam"), title="Lecture lente", severity="minor", service_ids=["s1"]
    )
    await incidents.resolve(support.p("sam"), slow.id, message="Fixed.")
    on_media = (await tool.handler(ai(people["ursula"]), {"service": "media", "days": 3})).data
    assert [i["title"] for i in on_media["resolved_lately"]] == ["Lecture lente"]  # the service's own
    assert on_media["resolved_lately"][0]["services"] == ["Media"]
    assert [i["title"] for i in on_media["in_progress"]] == ["Panne générale"]  # the whole portal's too
    on_books = (await tool.handler(ai(people["ursula"]), {"service": "books"})).data
    assert on_books["resolved_lately"] == []  # another service's incident is not this one's
