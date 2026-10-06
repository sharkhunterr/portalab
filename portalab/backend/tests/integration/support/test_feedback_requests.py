"""027 — feedback requests: an admin-defined form asked of members between two dates (one answer each,
``feedback.submitted`` with ``target = request`` from the member), staff replies shown in the member's list
(with a notification) and a request's results (counts, average rating, choices)."""

from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import text

from portalab.core.time import FixedClock
from tests.integration.identity.helpers import login
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration

SURVEY = {
    "kind": "survey",
    "label": "How is the new menu?",
    "description": "Two questions, one minute.",
    "requested": True,
    "fields": [
        {"key": "rating", "label": "Your rating", "type": "rating", "required": True},
        {"key": "clear", "label": "Is it clearer?", "type": "select", "options": ["yes", "no"]},
        {"key": "comment", "label": "Anything else?", "type": "long_text"},
    ],
}


async def test_request_cycle(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID], clock: FixedClock
) -> None:
    now = clock.now()
    await login(client, "boss")
    saved = await client.put(
        "/api/v1/admin/support/forms/menu_survey",
        json={
            **SURVEY,
            "opens_at": (now - timedelta(days=1)).isoformat(),
            "closes_at": (now + timedelta(days=7)).isoformat(),
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["requested"] is True

    await login(client, "ursula")
    assert "menu_survey" not in {f["key"] for f in (await client.get("/api/v1/feedback/forms")).json()}
    [request] = (await client.get("/api/v1/me/feedback/requests")).json()
    assert request["form"]["key"] == "menu_survey" and request["answered"] is False
    bad = await client.post("/api/v1/feedback", json={"form_key": "menu_survey", "values": {"rating": 7}})
    assert bad.status_code == 422
    sent = await client.post(
        "/api/v1/feedback",
        json={"form_key": "menu_survey", "values": {"rating": 4, "clear": "yes", "comment": "Nice"}},
    )
    assert sent.status_code == 201, sent.text
    again = await client.post("/api/v1/feedback", json={"form_key": "menu_survey", "values": {"rating": 5}})
    assert again.status_code == 409 and again.json()["code"] == "feedback.already_answered"
    assert (await client.get("/api/v1/me/feedback/requests")).json()[0]["answered"] is True
    async with support.full.database.session() as session:
        actor, target = (
            await session.execute(
                text(
                    "SELECT actor_id, metadata->>'target' FROM core.event_outbox "
                    "WHERE type = 'feedback.submitted' ORDER BY seq DESC LIMIT 1"
                )
            )
        ).one()
    assert actor == people["ursula"] and target == "request"

    await login(client, "ulrich")
    await client.post(
        "/api/v1/feedback", json={"form_key": "menu_survey", "values": {"rating": 2, "clear": "no"}}
    )

    await login(client, "boss")
    results = (await client.get("/api/v1/support/feedback/results/menu_survey")).json()
    by_key = {f["key"]: f for f in results["fields"]}
    assert results["total"] == 2 and by_key["rating"]["average"] == 3.0
    assert by_key["rating"]["counts"]["4"] == 1 and by_key["clear"]["counts"] == {"yes": 1, "no": 1}
    assert by_key["comment"]["latest"] == ["Nice"]
    replied = await client.post(
        f"/api/v1/support/feedback/{sent.json()['id']}/reply", json={"text": "Thanks!"}
    )
    assert replied.status_code == 200 and replied.json()["status"] == "reviewed"

    await login(client, "ursula")
    [mine] = (await client.get("/api/v1/me/feedback")).json()
    assert mine["reply"] == "Thanks!"
    assert any(n.template_key == "support:notify.feedbackReply" for n in support.outbox.sent)

    clock.set(now + timedelta(days=8))
    await login(client, "ursula")  # sessions expired meanwhile
    assert (await client.get("/api/v1/me/feedback/requests")).json() == []
    await login(client, "mona")
    closed = await client.post("/api/v1/feedback", json={"form_key": "menu_survey", "values": {"rating": 3}})
    assert closed.status_code == 409 and closed.json()["code"] == "feedback.request_closed"
