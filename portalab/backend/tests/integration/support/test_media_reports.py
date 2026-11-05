"""#354 — a problem reported on a media's page: the administrator's ticket type for it (one at most), a ticket
tied to the media, and its events telling it is about a media (a rule rewards the resolved ones)."""

from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text

from tests.integration.identity.helpers import login
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration

PROBLEM = {
    "key": "what",
    "label": "What is wrong",
    "type": "select",
    "options": ["Subtitles", "Sound", "Image"],
}


async def test_a_media_report_is_a_ticket_about_the_media(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    await login(client, "boss")
    first = await client.put("/api/v1/admin/support/types/old_reports", json={"label": "Old", "media": True})
    assert first.status_code == 200 and first.json()["media"] is True
    saved = await client.put(
        "/api/v1/admin/support/types/media_issue",
        json={"label": "Problem with a media", "fields": [PROBLEM], "media": True},
    )
    assert saved.status_code == 200, saved.text
    kinds = {t["key"]: t["media"] for t in (await client.get("/api/v1/admin/support/types")).json()}
    assert kinds["media_issue"] is True and kinds["old_reports"] is False  # one type takes them

    await login(client, "ursula")
    types = {t["key"]: t["media"] for t in (await client.get("/api/v1/tickets/types")).json()}
    assert types["media_issue"] is True and types["bug"] is False
    media = uuid4()
    created = await client.post(
        "/api/v1/tickets",
        json={
            "type_key": "media_issue",
            "title": "Problem with “Alien”",
            "fields": {"what": "Subtitles"},
            "media_id": str(media),
        },
    )
    assert created.status_code == 201, created.text
    ticket = created.json()
    assert ticket["media_id"] == str(media)
    assert [t["media_id"] for t in (await client.get("/api/v1/me/tickets")).json()] == [str(media)]

    await login(client, "sam")
    await client.post(f"/api/v1/tickets/{ticket['id']}/transition", json={"transition": "start"})
    resolved = await client.post(f"/api/v1/tickets/{ticket['id']}/transition", json={"transition": "resolve"})
    assert resolved.json()["state"] == "resolved"
    async with support.full.database.session() as session:
        rows = await session.execute(
            text(
                "SELECT type, metadata->>'media' FROM core.event_outbox WHERE type IN "
                "('ticket.created', 'ticket.resolved') ORDER BY seq"
            )
        )
        assert [tuple(r) for r in rows] == [("ticket.created", "true"), ("ticket.resolved", "true")]


async def test_a_ticket_without_media_says_so(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    created = await client.post("/api/v1/tickets", json={"type_key": "question", "title": "How?"})
    assert created.status_code == 201, created.text
    assert created.json()["media_id"] is None
    async with support.full.database.session() as session:
        media = await session.scalar(
            text("SELECT metadata->>'media' FROM core.event_outbox WHERE type = 'ticket.created'")
        )
    assert media == "false"
