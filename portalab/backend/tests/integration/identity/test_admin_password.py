"""#348 — an administrator sets a member's password: confirmed with their own, checked against the policy,
every session of the member signed out and the change audited; never their own account, the Admin's nor an
account of the single sign-on."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete

from portalab.modules.identity.models import Credential
from tests.integration.identity.helpers import PASSWORD, create_user, login, make_admin, module_of

pytestmark = pytest.mark.integration

NEW = "a brand new passphrase"  # test fixture value, not a real credential


async def test_admin_sets_a_member_password(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    admin_id = await make_admin(module)
    chloe = await create_user(module, "chloe")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as hers:
        assert (await login(hers, "chloe")).status_code == 200
        await login(client, "admin")
        url = f"/api/v1/users/{chloe}/password"

        wrong = await client.post(url, json={"password": "nope", "new_password": NEW})
        assert wrong.status_code == 422 and wrong.json()["code"] == "identity.password_current_wrong"
        assert (await client.get("/api/v1/me")).status_code == 200  # the administrator stays signed in
        short = await client.post(url, json={"password": PASSWORD, "new_password": "x"})
        assert short.status_code == 422

        done = await client.post(url, json={"password": PASSWORD, "new_password": NEW})
        assert done.status_code == 200, done.text
        assert done.json() == {"sessions_signed_out": 1}
        assert (await hers.get("/api/v1/me")).status_code == 401  # her session is signed out
        assert "identity.password_set_by_admin" in module.ctx.audit.actions()  # type: ignore[attr-defined]

        own = await client.post(
            f"/api/v1/users/{admin_id}/password", json={"password": PASSWORD, "new_password": NEW}
        )
        assert own.status_code == 409 and own.json()["code"] == "identity.password_own_account"

    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as fresh:
        assert (await login(fresh, "chloe")).status_code == 401
        assert (await login(fresh, "chloe", NEW)).status_code == 200


async def test_refused_for_a_member_or_a_single_sign_on_account(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    module = module_of(app)
    await make_admin(module)
    bob = await create_user(module, "bob")
    await create_user(module, "eve")
    await login(client, "eve")
    forbidden = await client.post(
        f"/api/v1/users/{bob}/password", json={"password": PASSWORD, "new_password": NEW}
    )
    assert forbidden.status_code == 403

    async with module.ctx.database.unit_of_work() as uow:  # bob's password now lives with the provider
        await uow.session.execute(delete(Credential).where(Credential.user_id == bob))
    await login(client, "admin")
    refused = await client.post(
        f"/api/v1/users/{bob}/password", json={"password": PASSWORD, "new_password": NEW}
    )
    assert refused.status_code == 409 and refused.json()["code"] == "identity.password_not_local"
