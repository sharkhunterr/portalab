"""Issue 512 — the one handling a ticket hears of it: assigned to them (an automation handing it to its own
author included), then every message, internal note, state change and file on it — never what they did
themselves. The team's queue counts the tickets per state and tells who opened each one, when, and who
handles it."""

from uuid import UUID

import httpx
import pytest

from portalab.capabilities.support import TicketRequest
from tests.authz_fixtures import automation
from tests.integration.identity.helpers import login
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration


def _told(support: SupportHarness, user: UUID) -> list[str]:
    return [r.template_key for r in support.outbox.sent if user in getattr(r.audience, "ids", ())]


async def test_the_assignee_hears_of_the_ticket_and_of_everything_on_it(
    support: SupportHarness, people: dict[str, UUID]
) -> None:
    sam, ursula = people["sam"], people["ursula"]
    ticket = (
        await support.module.tickets.create(support.p("ursula"), TicketRequest("question", "Help", ""))
    ).id
    action = support.actions.get("ticket.assign")
    assert action is not None
    await action.run({"ticket": str(ticket)}, automation(sam))
    assert _told(support, sam) == ["support:notify.assigned"]  # handed by their own automation: still news
    support.outbox.sent.clear()
    await support.module.tickets.comment(support.p("ursula"), ticket, "Any news?")
    await support.module.tickets.comment(support.p("boss"), ticket, "Looking", internal=True)
    await support.module.tickets.comment(support.p("sam"), ticket, "On it")  # their own: not to them
    await support.module.tickets.transition(support.p("ursula"), ticket, "cancel")
    assert _told(support, sam) == ["support:notify.comment", "support:notify.comment", "support:notify.state"]
    assert _told(support, ursula) == ["support:notify.comment"]  # the internal note never reaches her
    assert all(
        r.action_url == f"/support/queue/{ticket}"
        for r in support.outbox.sent
        if sam in getattr(r.audience, "ids", ())
    )


async def test_the_queue_counts_states_and_tells_who_and_when(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    first = await support.module.tickets.create(support.p("ursula"), TicketRequest("question", "One", ""))
    await support.module.tickets.create(support.p("ulrich"), TicketRequest("question", "Two", ""))
    await support.module.tickets.assign(support.p("sam"), first.id, people["sam"])
    await login(client, "sam")
    counts = (await client.get("/api/v1/support/tickets/counts")).json()["states"]
    assert counts["open"] >= 2
    unassigned = (await client.get("/api/v1/support/tickets/counts?unassigned=true")).json()["states"]
    assert unassigned["open"] == counts["open"] - 1
    items = {i["title"]: i for i in (await client.get("/api/v1/support/tickets?state=open")).json()["items"]}
    one = items["One"]
    assert one["requester_name"] and one["assignee_name"] and one["created_at"]
    assert items["Two"]["assignee_name"] is None and items["Two"]["requester_name"]
    await login(client, "ursula")
    assert (await client.get("/api/v1/support/tickets/counts")).status_code == 403
