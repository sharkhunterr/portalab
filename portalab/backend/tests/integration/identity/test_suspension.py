"""002 T033/T035 — suspend revokes sessions and blocks sign-in; reactivate restores; audited and evented;
dormancy marks Active → Inactive (data kept) and sign-in brings the account back."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.core.event_port import OutboxEvent
from portalab.core.time import FixedClock
from portalab.modules.identity.api.middleware import SESSION_COOKIE
from portalab.modules.identity.jobs import dormancy
from portalab.modules.identity.models import User
from tests.integration.identity.helpers import create_user, login, make_admin, module_of


@asynccontextmanager
async def _admin_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        assert (await login(http, "admin")).status_code == 200
        yield http


async def test_suspend_and_reactivate(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    await make_admin(module)
    user_id = await create_user(module, "mallory")
    assert (await login(client, "mallory")).status_code == 200
    harness_audit = module.ctx.audit

    async with _admin_client(app) as admin:
        suspended = await admin.post(f"/api/v1/users/{user_id}/suspend", json={"reason": "abuse"})
        assert suspended.status_code == 204
        # the user's existing session stops working on the next request
        assert (await client.get("/api/v1/me")).status_code == 401
        relog = await client.post(
            "/api/v1/auth/login", json={"login": "mallory", "password": "correct horse battery"}
        )
        assert relog.status_code == 403 and relog.json()["code"] == "auth.account_unavailable"

        reactivated = await admin.post(f"/api/v1/users/{user_id}/reactivate", json={"reason": "appeal"})
        assert reactivated.status_code == 204
    assert (await login(client, "mallory")).status_code == 200

    actions = harness_audit.actions()  # type: ignore[attr-defined]
    assert "user.suspended" in actions and "user.reactivated" in actions
    async with module.ctx.database.session() as session:
        events = list((await session.execute(select(OutboxEvent.type))).scalars())
    assert "user.suspended" in events and "user.reactivated" in events


async def test_admin_cannot_be_suspended_and_users_cannot_suspend(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    module = module_of(app)
    admin_id = await make_admin(module)
    await create_user(module, "trudy")
    async with _admin_client(app) as admin:
        refused = await admin.post(f"/api/v1/users/{admin_id}/suspend", json={"reason": "x"})
        assert refused.status_code == 409 and refused.json()["code"] == "admin.sole_admin_protected"
    await login(client, "trudy")
    forbidden = await client.post(f"/api/v1/users/{admin_id}/suspend", json={"reason": "x"})
    assert forbidden.status_code == 403


async def test_invalid_transition_is_a_problem(app: FastAPI) -> None:
    module = module_of(app)
    await make_admin(module)
    user_id = await create_user(module, "victor")
    async with _admin_client(app) as admin:
        response = await admin.post(f"/api/v1/users/{user_id}/reactivate", json={"reason": "noop"})
    assert response.status_code == 409
    assert response.json()["code"] == "user.state_transition_forbidden"


async def test_user_listing_is_paginated(app: FastAPI) -> None:
    module = module_of(app)
    await make_admin(module)
    for index in range(5):
        await create_user(module, f"member{index}")
    async with _admin_client(app) as admin:
        first = (await admin.get("/api/v1/users", params={"limit": 4})).json()
        second = (
            await admin.get("/api/v1/users", params={"limit": 4, "cursor": first["next_cursor"]})
        ).json()
        suspended_only = (await admin.get("/api/v1/users", params={"state": "suspended"})).json()
    assert len(first["items"]) == 4 and first["next_cursor"]
    assert len(second["items"]) == 2 and second["next_cursor"] is None
    assert suspended_only["items"] == []


async def test_dormancy_then_return(app: FastAPI, client: httpx.AsyncClient, clock: FixedClock) -> None:
    module = module_of(app)
    user_id = await create_user(module, "sleepy")
    await create_user(module, "busy")
    clock.advance(timedelta(days=module.ctx.config.dormancy_days - 1))
    assert (await login(client, "busy")).status_code == 200
    client.cookies.delete(SESSION_COOKIE)
    clock.advance(timedelta(days=2))
    assert await dormancy.run(module.ctx, module.accounts) == 1
    async with module.ctx.database.session() as session:
        user = await session.get(User, user_id)
        assert user is not None and user.state == "inactive" and user.display_name == "sleepy"
    directory = module.ctx.capabilities.system_providers("identity.directory")[0].provider
    assert await directory.is_active_account(user_id) is False

    assert (await login(client, "sleepy")).status_code == 200  # Inactive → Active on return
    assert await directory.is_active_account(user_id) is True
    assert await dormancy.run(module.ctx, module.accounts) == 0


pytestmark = pytest.mark.integration
