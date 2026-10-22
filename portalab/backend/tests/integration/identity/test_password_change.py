"""A member changes their own password: the current one is checked, the new one meets the policy, the other
sessions are signed out while this one stays; an account of the single sign-on has none to change."""

import httpx
import pytest
from fastapi import FastAPI

from tests.integration.identity.helpers import PASSWORD, create_user, login, module_of

pytestmark = pytest.mark.integration

NEW = "a brand new passphrase"  # test fixture value, not a real credential


async def test_change_own_password(app: FastAPI, client: httpx.AsyncClient) -> None:
    await create_user(module_of(app), "alice")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as phone:
        assert (await login(phone, "alice")).status_code == 200  # another device
        await login(client, "alice")

        wrong = await client.post(
            "/api/v1/me/password", json={"current_password": "nope", "new_password": NEW}
        )
        assert wrong.status_code == 422 and wrong.json()["code"] == "identity.password_current_wrong"
        same = await client.post(
            "/api/v1/me/password", json={"current_password": PASSWORD, "new_password": PASSWORD}
        )
        assert same.status_code == 422 and same.json()["code"] == "identity.password_unchanged"
        short = await client.post(
            "/api/v1/me/password", json={"current_password": PASSWORD, "new_password": "x"}
        )
        assert short.status_code == 422

        changed = await client.post(
            "/api/v1/me/password", json={"current_password": PASSWORD, "new_password": NEW}
        )
        assert changed.status_code == 200, changed.text
        assert changed.json() == {"other_sessions_signed_out": 1}
        assert (await client.get("/api/v1/me")).status_code == 200  # this session stays
        assert (await phone.get("/api/v1/me")).status_code == 401  # the other one is signed out

    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as fresh:
        assert (await login(fresh, "alice")).status_code == 401  # the old password no longer opens
        assert (await login(fresh, "alice", NEW)).status_code == 200


async def test_no_local_password(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    user_id = await create_user(module, "bob")
    await login(client, "bob")
    from sqlalchemy import delete

    from portalab.modules.identity.models import Credential

    async with module.ctx.database.unit_of_work() as uow:  # bob's password now lives with the provider
        await uow.session.execute(delete(Credential).where(Credential.user_id == user_id))
    refused = await client.post(
        "/api/v1/me/password", json={"current_password": PASSWORD, "new_password": NEW}
    )
    assert refused.status_code == 409 and refused.json()["code"] == "identity.password_not_local"
