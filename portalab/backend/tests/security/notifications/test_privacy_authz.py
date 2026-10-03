"""010 T028/T022 — a recipient who lost the required permission is suppressed (``permission_lost``); no
content in events, live pings or logs; the admin delivery view is metadata only; broadcast needs
``notifications.broadcast`` and is audited; the privacy participant exports and erases the inbox."""

import logging

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.notifications import CommunicationRequest, Users, declare_category
from portalab.modules.notifications.participant import NotificationsParticipant
from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.notifications.conftest import NotifyHarness

pytestmark = pytest.mark.integration
SECRET_TITLE = "Confidential-plan-xyz"


async def test_privacy_and_authority(
    app: FastAPI, client: httpx.AsyncClient, notify: NotifyHarness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    declare_category("media.new", "module:media", "media:category", registry=notify.categories)
    alex = await create_user(module_of(app), "alex")
    boss = await create_user(module_of(app), "boss")
    await make_admin(notify.ev.full, boss)
    await notify.module.send(
        CommunicationRequest(
            category="media.new",
            template_key="notifications:broadcast.message",
            audience=Users((alex, boss)),
            dedup_key="s1",
            params={"title": SECRET_TITLE, "body": ""},
            required_permission="audit.read",
        )
    )
    async with notify.database.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT user_id, status, suppress_reason FROM notify.deliveries WHERE channel = 'portal'"
                )
            )
        ).all()
    states = {r[0]: (r[1], r[2]) for r in rows}
    assert states[alex] == ("suppressed", "permission_lost") and states[boss] == ("delivered", None)
    await login(client, "alex")
    assert (
        await client.post(
            "/api/v1/admin/notifications/broadcast", json={"title": "Hello all", "dedup_key": "b-1"}
        )
    ).status_code == 403
    assert (await client.get("/api/v1/admin/notifications/deliveries")).status_code == 403
    await login(client, "boss")
    sent = await client.post(
        "/api/v1/admin/notifications/broadcast", json={"title": "Hello all", "dedup_key": "b-1"}
    )
    assert sent.status_code == 200 and sent.json()["recipients"] == 2
    listing = await client.get("/api/v1/admin/notifications/deliveries")
    assert listing.status_code == 200 and SECRET_TITLE not in listing.text and "title" not in listing.text
    async with notify.database.session() as session:
        audited = (
            await session.execute(
                text("SELECT count(*) FROM audit.audit_entries WHERE action = 'notifications.broadcast'")
            )
        ).scalar_one()
        events = (await session.execute(text("SELECT payload::text FROM events.events"))).scalars().all()
        live = (await session.execute(text("SELECT payload::text FROM core.live_event"))).scalars().all()
    assert audited == 1
    assert not any(SECRET_TITLE in p or "Hello all" in p for p in [*events, *live])
    assert SECRET_TITLE not in caplog.text
    participant = NotificationsParticipant(notify.database)
    exported = await participant.export(boss)
    assert {r.data["title"] for r in exported} >= {SECRET_TITLE}
    await participant.erase(boss, "delete")  # type: ignore[arg-type]
    await participant.erase(boss, "delete")  # type: ignore[arg-type] — idempotent
    assert await participant.export(boss) == []
    async with notify.database.session() as session:
        left = (
            await session.execute(
                text("SELECT count(*) FROM notify.deliveries WHERE user_id = :u"), {"u": boss}
            )
        ).scalar_one()
    assert left == 0
