"""010 T005/T009/T011/T014/T017 — the producer deduplicates per (source, dedup_key) and resolves the audience
under the caller's authority; the center lists important items first with unread counts, read, read-all,
archive and delete (several at once too, #112), owner-only; text is rendered in each recipient's language;
repeats about one subject are coalesced (critical never); a muted portal channel is suppressed while e-mail
is unaffected; a content-free live ping is published."""

from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.notifications import CommunicationRequest, Users, WithPermission, declare_category
from portalab.core.authz_port import Principal
from portalab.modules.administration.config.service import Change
from portalab.modules.notifications.producer.service import AudienceForbidden
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.notifications.conftest import NotifyHarness

pytestmark = pytest.mark.integration


def request(user: UUID, key: str, **extra: object) -> CommunicationRequest:
    values: dict[str, object] = {
        "category": "media.new",
        "template_key": "notifications:service.unavailable",
        "audience": Users((user,)),
        "dedup_key": key,
        "params": {"service": "Media"},
    }
    values.update(extra)
    return CommunicationRequest(**values)  # type: ignore[arg-type]


async def test_center(app: FastAPI, client: httpx.AsyncClient, notify: NotifyHarness) -> None:
    declare_category(
        "media.new",
        "module:media",
        "media:category",
        default_channels=("portal",),
        registry=notify.categories,
    )
    alex = await create_user(module_of(app), "alex")
    sam = await create_user(module_of(app), "sam")
    await notify.ev.full.administration.config.apply(
        [Change("i18n.language", "fr", "user", str(alex))], Principal(user_id=alex), admin_change=False
    )
    first = await notify.module.send(request(alex, "k1"))
    again = await notify.module.send(request(alex, "k1"))
    assert first.created and not again.created and first.id == again.id
    await notify.module.send(request(alex, "k2", subject_ref="media:1"))
    await notify.module.send(request(alex, "k3", subject_ref="media:1"))  # coalesced with k2
    await notify.module.send(
        request(alex, "k4", kind="alert", priority="critical", subject_ref="media:1")
    )  # never
    await login(client, "alex")
    page = (await client.get("/api/v1/me/notifications")).json()
    assert page["unread"] == 3
    assert page["items"][0]["priority"] == "critical"  # important first
    assert page["items"][0]["title"] == "Media est indisponible"  # rendered in French for alex
    assert sorted(i["count"] for i in page["items"]) == [1, 1, 2]
    # issue 242: read in the language of now (the interface's, when it says so), not the delivery's
    shown = (await client.get("/api/v1/me/notifications", params={"lang": "en"})).json()
    assert shown["items"][0]["title"] == "Media is unavailable"
    one = page["items"][-1]["id"]
    assert (await client.post(f"/api/v1/me/notifications/{one}/read")).json()["read"] is True
    assert (await client.get("/api/v1/me/notifications/unread-count")).json() == {"unread": 2}
    assert (await client.post(f"/api/v1/me/notifications/{one}/archive")).json()["archived"] is True
    assert len((await client.get("/api/v1/me/notifications")).json()["items"]) == 2
    assert (await client.post("/api/v1/me/notifications/read-all")).json() == {"read": 2}
    others = [i["id"] for i in (await client.get("/api/v1/me/notifications")).json()["items"]]
    await login(client, "sam")
    for method, path in (
        ("POST", f"/api/v1/me/notifications/{one}/read"),
        ("DELETE", f"/api/v1/me/notifications/{one}"),
    ):
        assert (await client.request(method, path)).status_code == 404  # never another user's item
    # #112: several at once — never another member's
    assert (
        await client.post("/api/v1/me/notifications/bulk", json={"ids": others, "action": "delete"})
    ).json() == {"done": 0}
    await login(client, "alex")
    bulk = "/api/v1/me/notifications/bulk"
    assert (await client.post(bulk, json={"ids": others, "action": "archive"})).json() == {"done": 2}
    assert (await client.get("/api/v1/me/notifications")).json()["items"] == []
    archived = (await client.get("/api/v1/me/notifications", params={"archived": True})).json()["items"]
    assert len(archived) == 3
    assert (await client.post(bulk, json={"ids": others, "action": "unarchive"})).json() == {"done": 2}
    assert len((await client.get("/api/v1/me/notifications")).json()["items"]) == 2
    assert (await client.post(bulk, json={"ids": others, "action": "delete"})).json() == {"done": 2}
    assert (await client.post(bulk, json={"ids": [], "action": "read"})).status_code == 422
    assert (await client.delete(f"/api/v1/me/notifications/{one}")).status_code == 204
    async with notify.database.session() as session:
        pings = (
            (
                await session.execute(
                    text("SELECT payload::text FROM core.live_event WHERE topic = 'notification.created'")
                )
            )
            .scalars()
            .all()
        )
    assert pings and all("title" not in p and "Media" not in p for p in pings)  # ids only
    del sam


async def test_preferences_and_authority(
    app: FastAPI, client: httpx.AsyncClient, notify: NotifyHarness
) -> None:
    declare_category(
        "media.new",
        "module:media",
        "media:category",
        default_channels=("portal",),
        registry=notify.categories,
    )
    alex = await create_user(module_of(app), "alex")
    sam = await create_user(module_of(app), "sam")
    await login(client, "alex")
    saved = await client.put(
        "/api/v1/me/notification-preferences",
        json={"preferences": {"media.new": {"portal": False, "email": True}}},
    )
    assert saved.status_code == 200
    channels = {c["key"]: c["channels"] for c in saved.json()["categories"]}["media.new"]
    assert channels["portal"]["enabled"] is False and channels["email"]["enabled"] is True
    refused = await client.put(
        "/api/v1/me/notification-preferences", json={"preferences": {"account.security": {"portal": False}}}
    )
    assert refused.status_code == 422 and refused.json()["code"] == "notifications.mandatory_channel"
    notify.module.config = __import__("dataclasses").replace(notify.module.config, email_enabled=True)
    await notify.module.send(request(alex, "p1"))
    async with notify.database.session() as session:
        rows = (
            await session.execute(
                text("SELECT channel, status, suppress_reason FROM notify.deliveries ORDER BY channel")
            )
        ).all()
    assert [tuple(r) for r in rows] == [
        ("email", "suppressed", "no_address"),
        ("portal", "suppressed", "preference"),
    ]
    with pytest.raises(AudienceForbidden):
        await notify.module.send(request(sam, "p2"), caller=Principal(user_id=alex))  # another user
    with pytest.raises(AudienceForbidden):
        await notify.module.send(
            request(alex, "p3", audience=WithPermission("audit.read")), caller=Principal(user_id=alex)
        )
    mine = await notify.module.send(request(alex, "p4"), caller=Principal(user_id=alex))  # oneself is fine
    assert mine.created
