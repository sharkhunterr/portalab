"""012 T013 — community events: create/edit/cancel (title, sanitized Markdown, start/end or all-day,
reference time zone, audience tier) by ``community.events.manage`` holders, audited; visibility per audience;
``community.event_created|updated|cancelled`` emitted once per version; the ``community_event`` calendar
source returns only permitted events with source links; cancelled events show as cancelled; reminders
re-check ``item``."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.i18n import LocaleContext
from tests.integration.community.conftest import CoHarness
from tests.integration.identity.helpers import login
from tests.integration.privacy.conftest import NOW

pytestmark = pytest.mark.integration


def body(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "title": "Movie night",
        "description_md": "Bring snacks <script>alert(1)</script> **please**",
        "starts_at": (NOW + timedelta(days=2)).isoformat(),
        "ends_at": (NOW + timedelta(days=2, hours=3)).isoformat(),
        "reference_tz": "Europe/Paris",
        "audience": "community",
    }
    data.update(overrides)
    return data


async def test_lifecycle_and_audience(co: CoHarness, client: AsyncClient) -> None:
    await login(client, "ursula")
    assert (await client.post("/api/v1/community/events", json=body())).status_code == 403
    await login(client, "mona")
    created = await client.post("/api/v1/community/events", json=body())
    assert created.status_code == 201, created.text
    event = created.json()
    assert "<script>" not in event["rendered_html"] and "<strong>please</strong>" in event["rendered_html"]
    staff = (
        await client.post(
            "/api/v1/community/events",
            json=body(title="Staff sync", audience="roles", audience_roles=["support"]),
        )
    ).json()
    for invalid in (
        body(reference_tz="Mars/Olympus"),
        body(ends_at=(NOW - timedelta(days=1)).isoformat()),
        body(audience="roles"),
        body(title=""),
    ):
        assert (await client.post("/api/v1/community/events", json=invalid)).status_code == 422
    updated = await client.patch(f"/api/v1/community/events/{event['id']}", json=body(title="Film night"))
    assert updated.json()["title"] == "Film night" and updated.json()["version"] == 2

    window = {"start": NOW.isoformat(), "end": (NOW + timedelta(days=7)).isoformat()}
    await login(client, "ulrich")
    titles = [e["title"] for e in (await client.get("/api/v1/community/events", params=window)).json()]
    assert titles == ["Film night"]  # not in the role audience
    assert (await client.get(f"/api/v1/community/events/{staff['id']}")).status_code == 404
    await login(client, "mona")  # managers see every event
    assert len((await client.get("/api/v1/community/events", params=window)).json()) == 2

    calendar = co.module.events
    result = await calendar.items(NOW, NOW + timedelta(days=7), co.p("ulrich"), LocaleContext())
    [item] = result.items
    assert item.source_kind == "community_event" and item.url_ref == f"/community/events/{event['id']}"
    assert await calendar.item(staff["id"], co.p("ulrich")) is None
    cancelled = await client.post(f"/api/v1/community/events/{event['id']}/cancel")
    assert cancelled.json()["status"] == "cancelled"
    again = await client.post(f"/api/v1/community/events/{event['id']}/cancel")
    assert again.json()["version"] == cancelled.json()["version"]  # once
    reminder = await calendar.item(event["id"], co.p("ulrich"))
    assert reminder is not None and reminder.status == "cancelled"
    assert (await client.patch(f"/api/v1/community/events/{event['id']}", json=body())).status_code == 409

    async with co.database.session() as session:
        emitted = (
            await session.execute(
                text("SELECT type, payload::text FROM events.events WHERE type LIKE 'community.event_%'")
            )
        ).all()
        audited = (
            (
                await session.execute(
                    text("SELECT action FROM audit.audit_entries WHERE action LIKE 'community.%'")
                )
            )
            .scalars()
            .all()
        )
    assert sorted(t for t, _ in emitted) == [
        "community.event_cancelled",
        "community.event_created",
        "community.event_created",
        "community.event_updated",
    ]
    assert all("Movie" not in p and "snacks" not in p for _, p in emitted)
    assert len(audited) == 4


async def test_all_day(co: CoHarness, client: AsyncClient) -> None:
    await login(client, "boss")
    start = NOW.replace(hour=22) + timedelta(days=1)  # 23:00 UTC is the next day in Paris
    created = await client.post(
        "/api/v1/community/events",
        json=body(all_day=True, starts_at=start.isoformat(), ends_at=None, audience="public"),
    )
    assert created.status_code == 201
    item = await co.module.events.item(created.json()["id"], co.p("ulrich"))
    assert item is not None and item.all_day and item.date == (NOW + timedelta(days=2)).date()
