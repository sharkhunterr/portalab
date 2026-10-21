"""027 — an announcement goes out through the channels the administrator picks (notification, e-mail,
banner — any of them); a banner shows until its date or until it is ended."""

from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.core.time import FixedClock
from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.notifications.conftest import NotifyHarness

pytestmark = pytest.mark.integration


async def test_channels_and_banner(
    app: FastAPI, client: httpx.AsyncClient, notify: NotifyHarness, clock: FixedClock
) -> None:
    boss = await create_user(module_of(app), "boss")
    await make_admin(notify.ev.full, boss)
    await create_user(module_of(app), "alex")
    await login(client, "boss")
    banner_only = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={
            "title": "Portal moving",
            "body": "New address next week.",
            "dedup_key": "a-1",
            "channels": ["banner"],
            "tone": "warning",
            "banner_until": (clock.now() + timedelta(days=2)).isoformat(),
        },
    )
    assert banner_only.status_code == 200, banner_only.text
    assert banner_only.json()["communication"] is None  # no notification asked
    both = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"title": "Movie night", "dedup_key": "a-2", "channels": ["notification", "email"]},
    )
    assert both.status_code == 200 and both.json()["recipients"] == 2
    async with notify.database.session() as session:
        categories = (
            (await session.execute(text("SELECT category FROM notify.communications ORDER BY created_at")))
            .scalars()
            .all()
        )
    assert categories == ["communications.broadcast", "communications.announcement_email"]

    await login(client, "alex")
    [shown] = (await client.get("/api/v1/announcements/banners")).json()
    assert shown["title"] == "Portal moving" and shown["tone"] == "warning"
    clock.set(clock.now() + timedelta(days=3))
    await login(client, "alex")
    assert (await client.get("/api/v1/announcements/banners")).json() == []

    await login(client, "boss")
    listed = (await client.get("/api/v1/admin/announcements")).json()
    assert [a["channels"] for a in listed] == [["notification", "email"], ["banner"]]
    again = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"title": "Open house", "dedup_key": "a-3", "channels": ["banner"]},
    )
    ended = await client.post(f"/api/v1/admin/announcements/{again.json()['announcement']}/end")
    assert ended.status_code == 200 and ended.json()["ended_at"]
    assert (await client.get("/api/v1/announcements/banners")).json() == []


async def test_a_banner_members_cannot_close(
    app: FastAPI, client: httpx.AsyncClient, notify: NotifyHarness
) -> None:
    boss = await create_user(module_of(app), "boss")
    await make_admin(notify.ev.full, boss)
    await login(client, "boss")
    for key, dismissible in (("s-1", None), ("s-2", False)):
        sent = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"title": f"Banner {key}", "dedup_key": key, "channels": ["banner"]}
            | ({} if dismissible is None else {"banner_dismissible": dismissible}),
        )
        assert sent.status_code == 200, sent.text
    shown = {b["title"]: b["dismissible"] for b in (await client.get("/api/v1/announcements/banners")).json()}
    assert shown == {"Banner s-1": True, "Banner s-2": False}  # closable unless the administrator says not
