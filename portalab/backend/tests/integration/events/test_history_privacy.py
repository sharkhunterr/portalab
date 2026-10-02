"""007 T020/T022 — history: the owner sees their own history; another permitted user sees nothing private;
events of a disconnected service remain; the admin payload view is redacted below the Admin level."""

from datetime import UTC, datetime

import httpx
from fastapi import FastAPI

from portalab.capabilities.events import EventType
from portalab.core.authz_port import Principal
from portalab.core.event_port import SubjectRef
from tests.authz_fixtures import make_admin
from tests.events_fixtures import EventsHarness
from tests.integration.identity.helpers import create_user, login, module_of

OCCURRED = datetime(2026, 9, 1, tzinfo=UTC)


async def _seed(ev: EventsHarness, owner: object) -> None:
    ev.types.register(EventType("media.watched", "t", visibility_class="private"))
    ev.types.register(EventType("project.created", "t", visibility_class="public"))
    async with ev.full.database.unit_of_work() as uow:
        for index in range(3):
            await ev.publisher.publish(
                uow.session,
                "media.watched",
                {"service_id": "plex-gone", "n": index},
                occurred_at=OCCURRED,
                actor=Principal(user_id=owner),  # type: ignore[arg-type]
                subject=SubjectRef("user", str(owner)),
            )
        await ev.publisher.publish(
            uow.session,
            "project.created",
            {"project_ref": "p1"},
            occurred_at=OCCURRED,
            actor=Principal(user_id=owner),
            subject=SubjectRef("project", "p1"),
        )  # type: ignore[arg-type]


async def test_history_views(app: FastAPI, client: httpx.AsyncClient, ev: EventsHarness) -> None:
    app.state.events_module = ev.module
    owner = await create_user(module_of(app), "owner")
    await create_user(module_of(app), "other")
    await _seed(ev, owner)

    await login(client, "owner")
    page = (await client.get("/api/v1/me/history", params={"limit": 2})).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = (await client.get("/api/v1/me/history", params={"cursor": page["next_cursor"]})).json()
    assert {i["type"] for i in page["items"] + rest["items"]} == {"media.watched", "project.created"}
    assert any(i["payload"].get("service_id") == "plex-gone" for i in page["items"] + rest["items"])

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as other:
        await login(other, "other")
        seen = (await other.get(f"/api/v1/subjects/user/{owner}/history")).json()
        assert seen["items"] == []  # nothing private by permission alone
        unknown = await other.get("/api/v1/subjects/project/p1/history")
        assert unknown.status_code == 404  # subject types become readable when their module registers them
        assert (await other.get("/api/v1/admin/events")).status_code == 403


async def test_admin_view_redaction(app: FastAPI, client: httpx.AsyncClient, ev: EventsHarness) -> None:
    app.state.events_module = ev.module
    owner = await create_user(module_of(app), "owner")
    admin_id = await create_user(module_of(app), "boss")
    await make_admin(ev.full, admin_id)
    await _seed(ev, owner)
    await login(client, "boss")
    full_view = (await client.get("/api/v1/admin/events", params={"type": "media."})).json()["items"]
    assert full_view[0]["payload"]["service_id"] == "plex-gone" and full_view[0]["actor_user_id"] == str(
        owner
    )
    from portalab.modules.authz.grants.service import GrantSpec
    from portalab.modules.authz.models import BASE_ROLE_IDS
    from tests.authz_fixtures import user

    await ev.full.authz.grants.add_grant(None, "role", BASE_ROLE_IDS["support"], GrantSpec("events.manage"))
    helper = await create_user(module_of(app), "helper")
    await ev.full.authz.grants.assign_role(user(admin_id), helper, "support")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as support:
        await login(support, "helper")
        limited = (await support.get("/api/v1/admin/events", params={"type": "media."})).json()["items"]
    assert limited[0]["payload"] == {"redacted": True, "keys": ["n", "service_id"]}
    assert limited[0]["actor_user_id"] is None
