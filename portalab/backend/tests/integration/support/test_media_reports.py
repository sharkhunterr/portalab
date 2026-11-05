"""#354 — a problem reported on a media's page: the administrator's ticket type for it (one at most), a ticket
tied to the media, and its events telling it is about a media (a rule rewards the resolved ones)."""

from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import text

from portalab.capabilities.media_core import TECHNICAL_SHEETS
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


async def test_a_portal_takes_media_reports_from_the_start(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    await login(client, "ursula")
    types = {t["key"]: t["media"] for t in (await client.get("/api/v1/tickets/types")).json()}
    assert types["media_issue"] is True and sum(types.values()) == 1
    # seeded again at every start: an administrator's choice stays
    await login(client, "boss")
    await client.put("/api/v1/admin/support/types/mine", json={"label": "Mine", "media": True})
    await support.module.definitions.ensure_baseline()
    kinds = {t["key"]: t["media"] for t in (await client.get("/api/v1/admin/support/types")).json()}
    assert kinds["mine"] is True and kinds["media_issue"] is False


async def test_a_media_s_tickets_on_its_page(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    media = uuid4()
    await login(client, "ursula")
    made = await client.post(
        "/api/v1/tickets",
        json={"type_key": "media_issue", "title": "Sound — “Alien”", "media_id": str(media)},
    )
    assert made.status_code == 201, made.text
    mine = (await client.get(f"/api/v1/tickets/media/{media}")).json()
    assert mine["open"] == 1 and mine["items"][0]["mine"] is True and mine["staff"] is False

    await login(client, "ulrich")  # a private type: another member sees nothing of it
    assert (await client.get(f"/api/v1/tickets/media/{media}")).json() == {
        "open": 0,
        "closed": 0,
        "staff": False,
        "items": [],
    }
    await login(client, "boss")
    shared = await client.put(
        "/api/v1/admin/support/types/media_issue",
        json={"label": "A problem with a media", "media": True, "public": True},
    )
    assert shared.json()["public"] is True
    await login(client, "ulrich")
    seen = (await client.get(f"/api/v1/tickets/media/{media}")).json()
    assert (
        seen["open"] == 1
        and seen["items"][0]["title"] == "Sound — “Alien”"
        and seen["items"][0]["mine"] is False
    )
    assert set(seen["items"][0]) == {
        "id",
        "reference",
        "title",
        "state",
        "open",
        "mine",
        "created_at",
        "updated_at",
    }

    await login(client, "sam")  # the team: all, and resolves it
    assert (await client.get(f"/api/v1/tickets/media/{media}")).json()["staff"] is True
    tid = made.json()["id"]
    await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": "start"})
    await client.post(f"/api/v1/tickets/{tid}/transition", json={"transition": "resolve"})
    await login(client, "ulrich")
    after = (await client.get(f"/api/v1/tickets/media/{media}")).json()
    assert after["open"] == 0 and after["closed"] == 1 and after["items"] == []  # the closed ones on demand
    every = (await client.get(f"/api/v1/tickets/media/{media}?closed=true")).json()
    assert [t["open"] for t in every["items"]] == [False]


class Sheets:
    def __init__(self) -> None:
        self.asked: list[UUID] = []

    async def sheet(self, viewer: Any, object_id: UUID) -> dict[str, Any]:
        self.asked.append(object_id)
        return {"servers": [{"service": "Plex", "added_at": None, "files": []}], "acquisition": None}


async def test_the_team_reads_the_media_s_technical_sheet(
    client: httpx.AsyncClient, support: SupportHarness, people: dict[str, UUID]
) -> None:
    sheets = Sheets()
    support.module.capabilities.provide(TECHNICAL_SHEETS, sheets, instance_ref="media", owner="test")
    media = uuid4()
    await login(client, "ursula")
    about = await client.post(
        "/api/v1/tickets",
        json={"type_key": "media_issue", "title": "Sound — “Alien”", "media_id": str(media)},
    )
    other = await client.post("/api/v1/tickets", json={"type_key": "question", "title": "How?"})
    hidden = await client.get(f"/api/v1/tickets/{about.json()['id']}/media-sheet")
    assert hidden.status_code == 403  # the team's only
    await login(client, "sam")
    sheet = await client.get(f"/api/v1/tickets/{about.json()['id']}/media-sheet")
    assert sheet.status_code == 200 and sheet.json()["servers"][0]["service"] == "Plex"
    assert sheets.asked == [media]
    none = await client.get(f"/api/v1/tickets/{other.json()['id']}/media-sheet")
    assert none.status_code == 404 and none.json()["code"] == "ticket.no_media"
