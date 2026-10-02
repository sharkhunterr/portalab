"""002 T046 — Admin transfer: exactly one Admin before/after, concurrent transfers ⇒ one winner, step-up
re-authentication, never zero Admins, second-Admin and delegation attempts refused."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict
from portalab.core.event_port import OutboxEvent
from portalab.modules.identity.models import UserSession
from tests.integration.identity.helpers import PASSWORD, create_user, login, make_admin, module_of

pytestmark = pytest.mark.integration


async def test_transfer_moves_the_single_admin(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    admin_id = await make_admin(module)
    heir = await create_user(module, "heir")
    await login(client, "admin")

    no_reauth = await client.post(
        "/api/v1/admin/transfer", json={"target_user_id": str(heir), "password": "wrong!"}
    )
    assert no_reauth.status_code == 401
    assert module.ctx.capabilities.system_providers("authz.admin_authority")[0].provider.admin == admin_id

    done = await client.post(
        "/api/v1/admin/transfer", json={"target_user_id": str(heir), "password": PASSWORD}
    )
    assert done.status_code == 204
    authority = module.ctx.capabilities.system_providers("authz.admin_authority")[0].provider
    assert authority.admin == heir and authority.transfers == [(admin_id, heir)]
    assert "user.admin_transferred" in module.ctx.audit.actions()  # type: ignore[attr-defined]
    async with module.ctx.database.session() as session:
        assert "user.admin_transferred" in (await session.execute(select(OutboxEvent.type))).scalars().all()

    # the former Admin lost the permission immediately (evaluated per request)
    again = await client.post(
        "/api/v1/admin/transfer", json={"target_user_id": str(admin_id), "password": PASSWORD}
    )
    assert again.status_code == 403


async def test_temporary_delegation_is_refused(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    await make_admin(module)
    heir = await create_user(module, "heir")
    await login(client, "admin")
    response = await client.post(
        "/api/v1/admin/transfer",
        json={"target_user_id": str(heir), "password": PASSWORD, "until": "2026-10-02T00:00:00Z"},
    )
    assert response.status_code == 422  # no temporary/time-boxed form exists


async def test_transfer_to_inactive_or_self_is_refused(app: FastAPI, client: httpx.AsyncClient) -> None:
    from portalab.modules.identity.domain.state_machine import AccountState

    module = module_of(app)
    admin_id = await make_admin(module)
    pending = await create_user(module, "pending", state=AccountState.PENDING_VERIFICATION)
    await login(client, "admin")
    for target in (pending, admin_id):
        response = await client.post(
            "/api/v1/admin/transfer", json={"target_user_id": str(target), "password": PASSWORD}
        )
        assert response.status_code == 409


async def test_concurrent_transfers_have_one_winner(app: FastAPI) -> None:
    module = module_of(app)
    admin_id = await make_admin(module)
    heirs = [await create_user(module, f"heir{i}") for i in range(4)]
    principal = Principal(user_id=admin_id)
    results = await asyncio.gather(
        *(module.admin.transfer_admin(principal, heir) for heir in heirs), return_exceptions=True
    )
    successes = [result for result in results if not isinstance(result, BaseException)]
    assert len(successes) == 1
    assert all(isinstance(result, Conflict) for result in results if isinstance(result, BaseException))
    authority = module.ctx.capabilities.system_providers("authz.admin_authority")[0].provider
    assert authority.admin in heirs and len(authority.transfers) == 1


async def test_second_admin_and_zero_admin_are_impossible(app: FastAPI) -> None:
    module = module_of(app)
    await make_admin(module)
    other = await create_user(module, "other")
    with pytest.raises(Conflict) as caught:
        await module.bootstrap.create_first_admin(login="intruder", password=PASSWORD)
    assert caught.value.code == "admin.already_exists"
    async with module.ctx.database.session() as session:
        with pytest.raises(Exception, match="Admin"):
            await module.ctx.admin_authority().grant_first_admin(session, other)


async def test_transfer_ends_the_former_admins_other_sessions(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    module = module_of(app)
    admin_id = await make_admin(module)
    heir = await create_user(module, "heir")
    second = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://portal.test")
    async with second:
        await login(second, "admin")
        await login(client, "admin")
        await client.post("/api/v1/admin/transfer", json={"target_user_id": str(heir), "password": PASSWORD})
        assert (await second.get("/api/v1/me")).status_code == 401
    assert (await client.get("/api/v1/me")).status_code == 200
    async with module.ctx.database.session() as session:
        reasons = (
            (await session.execute(select(UserSession.revoke_reason).where(UserSession.user_id == admin_id)))
            .scalars()
            .all()
        )
    assert sorted(reasons, key=str) == sorted(["admin", None], key=str)
