"""Issue 508 — ``ticket.assign``: an automation hands a ticket to someone, by default its own author
(« assign to me »); a ticket a person already took is left alone unless the rule says ``reassign``; an
author without ``tickets.manage`` assigns nothing. The « new ticket: assign it to me » template is offered,
never installed: it uses the action with the new ticket's id only."""

from uuid import UUID

import pytest

from portalab.capabilities.support import TicketRequest
from portalab.core.errors import ValidationFailed
from portalab.modules.automations.templates.loader import load
from tests.authz_fixtures import automation
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration


async def _ticket(support: SupportHarness) -> UUID:
    made = await support.module.tickets.create(support.p("ursula"), TicketRequest("question", "Help", ""))
    return made.id


async def _assignee(support: SupportHarness, ticket: UUID) -> UUID | None:
    return (await support.module.tickets.view(ticket, support.p("sam"))).ticket.assignee_id


async def test_a_rule_assigns_a_new_ticket_to_its_author(
    support: SupportHarness, people: dict[str, UUID]
) -> None:
    action = support.actions.get("ticket.assign")
    assert action is not None and action.required_params() == ("ticket",)
    ticket = await _ticket(support)
    done = await action.run({"ticket": str(ticket)}, automation(people["sam"]))
    assert done == {"ticket": str(ticket), "assignee": str(people["sam"]), "changed": True}
    assert await _assignee(support, ticket) == people["sam"]


async def test_a_taken_ticket_is_left_to_its_assignee_unless_reassigned(
    support: SupportHarness, people: dict[str, UUID]
) -> None:
    action = support.actions.get("ticket.assign")
    assert action is not None
    ticket = await _ticket(support)
    await support.module.tickets.assign(support.p("sam"), ticket, people["mona"])
    kept = await action.run({"ticket": str(ticket)}, automation(people["sam"]))
    assert kept["changed"] is False and await _assignee(support, ticket) == people["mona"]
    moved = await action.run({"ticket": str(ticket), "reassign": True}, automation(people["sam"]))
    assert moved["changed"] is True and await _assignee(support, ticket) == people["sam"]
    named = await action.run(
        {"ticket": str(ticket), "assignee": str(people["mona"]), "reassign": True}, automation(people["sam"])
    )
    assert named["assignee"] == str(people["mona"]) and await _assignee(support, ticket) == people["mona"]


async def test_only_support_staff_rules_assign(support: SupportHarness, people: dict[str, UUID]) -> None:
    action = support.actions.get("ticket.assign")
    assert action is not None
    ticket = await _ticket(support)
    with pytest.raises(Exception):  # noqa: B017 — the author is no support staff: the ticket stays hidden
        await action.run({"ticket": str(ticket)}, automation(people["ulrich"]))
    with pytest.raises(ValidationFailed):
        await action.run({"ticket": "not-an-id"}, automation(people["sam"]))
    assert await _assignee(support, ticket) is None


async def test_the_assign_to_me_template_is_offered_with_the_new_tickets_id(support: SupportHarness) -> None:
    template = next(t for t in load() if t.key == "new-ticket-assign-to-me")
    definition = template.definition
    assert definition["trigger"] == {"kind": "event", "event_type": "ticket.created"}
    [step] = definition["steps"]
    action = support.actions.get(step["action"])
    assert action is not None
    assert set(step["params"]) <= set(action.params_schema)
    assert set(action.required_params()) <= set(step["params"])
    assert step["params"]["ticket"] == "${event.ticket}"  # ticket.created carries the ticket's id
