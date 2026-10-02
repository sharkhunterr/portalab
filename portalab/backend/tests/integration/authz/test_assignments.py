"""003 T020 — role and group assignments take effect on the next request, revocation withdraws, every
change emits a ``permission.*`` event and an audit entry."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy import select, text

from portalab.core.event_port import OutboxEvent
from portalab.modules.authz.models import AuditEntry
from tests.authz_fixtures import AuthzPlatform, make_admin
from tests.integration.identity.helpers import create_user, login, module_of


@asynccontextmanager
async def signed_in(app: FastAPI, login_: str) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        assert (await login(http, login_)).status_code == 200
        yield http


async def _events(platform: AuthzPlatform) -> list[str]:
    async with platform.database.session() as session:
        return list((await session.execute(select(OutboxEvent.type).order_by(OutboxEvent.seq))).scalars())


async def test_role_assignment_and_revocation(app: FastAPI, platform: AuthzPlatform) -> None:
    identity = module_of(app)
    admin_id = await create_user(identity, "admin")
    await make_admin(platform, admin_id)
    editor_id = await create_user(identity, "eddie")

    async with signed_in(app, "eddie") as eddie, signed_in(app, "admin") as admin:
        roles = (await admin.get("/api/v1/roles")).json()
        assert {role["key"] for role in roles} >= {"user", "support", "moderator", "editor", "admin"}
        before = (await eddie.get("/api/v1/me/permissions")).json()
        assert "news.publish" not in before["permissions"]

        assert (
            await admin.post(f"/api/v1/users/{editor_id}/roles", json={"role_key": "editor"})
        ).status_code == 204
        after = (await eddie.get("/api/v1/me/permissions")).json()  # next request: no cache
        assert "news.publish" in after["permissions"] and "editor" in after["roles"]
        assert [r["key"] for r in (await admin.get(f"/api/v1/users/{editor_id}/roles")).json()] == ["editor"]

        duplicate = await admin.post(f"/api/v1/users/{editor_id}/roles", json={"role_key": "editor"})
        assert duplicate.status_code == 409

        assert (await admin.delete(f"/api/v1/users/{editor_id}/roles/editor")).status_code == 204
        assert "news.publish" not in (await eddie.get("/api/v1/me/permissions")).json()["permissions"]

    events = await _events(platform)
    assert "permission.role_assigned" in events and "permission.role_revoked" in events
    async with platform.database.session() as session:
        actions = set((await session.execute(select(AuditEntry.action))).scalars())
    assert {"permission.role_assigned", "permission.role_revoked"} <= actions


async def test_group_membership_grants_group_permissions(app: FastAPI, platform: AuthzPlatform) -> None:
    identity = module_of(app)
    admin_id = await create_user(identity, "admin")
    await make_admin(platform, admin_id)
    member_id = await create_user(identity, "gina")
    async with signed_in(app, "admin") as admin, signed_in(app, "gina") as gina:
        group = (
            await admin.post("/api/v1/groups", json={"key": "moderators-fr", "name": "Modérateurs"})
        ).json()
        grant = await admin.post(
            f"/api/v1/groups/{group['id']}/grants", json={"permission_key": "tickets.manage"}
        )
        assert grant.status_code == 201
        assert "tickets.manage" not in (await gina.get("/api/v1/me/permissions")).json()["permissions"]
        assert (
            await admin.post(f"/api/v1/users/{member_id}/groups", json={"group_key": "moderators-fr"})
        ).status_code == 204
        assert "tickets.manage" in (await gina.get("/api/v1/me/permissions")).json()["permissions"]
        assert (await admin.delete(f"/api/v1/users/{member_id}/groups/moderators-fr")).status_code == 204
        assert "tickets.manage" not in (await gina.get("/api/v1/me/permissions")).json()["permissions"]
        not_empty = await admin.delete(f"/api/v1/groups/{group['id']}")
        assert not_empty.status_code == 204
    assert "permission.group_changed" in await _events(platform)


async def test_custom_role_lifecycle_and_base_roles_are_protected(
    app: FastAPI, platform: AuthzPlatform
) -> None:
    identity = module_of(app)
    admin_id = await create_user(identity, "admin")
    await make_admin(platform, admin_id)
    member_id = await create_user(identity, "carl")
    async with signed_in(app, "admin") as admin:
        role = (await admin.post("/api/v1/roles", json={"key": "librarian", "name": "Librarian"})).json()
        assert role["key"] == "custom:librarian" and role["kind"] == "custom"
        await admin.post(f"/api/v1/roles/{role['id']}/grants", json={"permission_key": "wiki.edit"})
        await admin.post(f"/api/v1/users/{member_id}/roles", json={"role_key": "custom:librarian"})
        assigned = await admin.delete(f"/api/v1/roles/{role['id']}")
        assert assigned.status_code == 409 and assigned.json()["code"] == "authz.role_assigned"
        await admin.delete(f"/api/v1/users/{member_id}/roles/custom:librarian")
        assert (await admin.delete(f"/api/v1/roles/{role['id']}")).status_code == 204
        async with platform.database.session() as session:
            editor_id = await session.scalar(text("SELECT id FROM authz.roles WHERE key = 'editor'"))
        base = await admin.delete(f"/api/v1/roles/{editor_id}")
        assert base.status_code == 409 and base.json()["code"] == "authz.base_role"
