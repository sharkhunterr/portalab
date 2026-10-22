"""#98: the support's badges — a ticket waiting for the team, feedback not read yet, an incident under way —
counted for those who may handle them; a member sees nothing."""

from uuid import UUID

import httpx

from portalab.modules.support.attention import SupportAttention
from tests.integration.identity.helpers import login
from tests.integration.support.conftest import SupportHarness


async def test_what_waits_for_the_team(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    attention = SupportAttention(support.module.database, support.module.authorizer)
    calm = await attention.counts(support.p("boss"))
    assert calm == {"support.queue": 0, "support.feedback_review": 0, "support.incident_console": 0}

    await login(client, "ursula")
    ticket = await client.post(
        "/api/v1/tickets",
        json={"type_key": "bug", "title": "Crash", "description": "It crashes", "fields": {"steps": "Play"}},
    )
    assert ticket.status_code == 201, ticket.text
    sent = await client.post("/api/v1/feedback", json={"form_key": "general", "values": {"message": "Nice"}})
    assert sent.status_code in (200, 201), sent.text
    await support.module.incidents.create(
        support.p("sam"), title="Media playback broken", severity="major", service_ids=["s1"]
    )

    assert await attention.counts(support.p("boss")) == {
        "support.queue": 1,
        "support.feedback_review": 1,
        "support.incident_console": 1,
    }
    assert await attention.counts(support.p("ursula")) == {}
