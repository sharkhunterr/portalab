"""027 — an administrator corrects a member's display name or e-mail: unique display name, e-mail cleared with
an empty string, audited without the values, and reserved to ``users.manage``."""

import httpx
from fastapi import FastAPI

from tests.integration.identity.helpers import create_user, login, make_admin, module_of


async def test_admin_edits_a_member(app: FastAPI, client: httpx.AsyncClient) -> None:
    module = module_of(app)
    await make_admin(module)
    zoe = await create_user(module, "zoe")
    await create_user(module, "max")
    await login(client, "admin")

    edited = await client.patch(
        f"/api/v1/users/{zoe}", json={"display_name": "Zoé M.", "email": "zoe@home.lan"}
    )
    assert edited.status_code == 200
    assert edited.json()["display_name"] == "Zoé M." and edited.json()["email"] == "zoe@home.lan"
    listed = {u["login"]: u for u in (await client.get("/api/v1/users")).json()["items"]}
    assert listed["zoe"]["email"] == "zoe@home.lan"

    taken = await client.patch(f"/api/v1/users/{zoe}", json={"display_name": "max"})
    assert taken.status_code == 409 and taken.json()["code"] == "user.display_name_taken"
    assert (await client.patch(f"/api/v1/users/{zoe}", json={"email": "not-an-email"})).status_code == 422

    cleared = await client.patch(f"/api/v1/users/{zoe}", json={"email": ""})
    assert cleared.json()["email"] is None and cleared.json()["display_name"] == "Zoé M."

    audit = module.ctx.audit
    assert "user.admin_edited" in audit.actions()  # type: ignore[attr-defined]

    await login(client, "max")
    assert (await client.patch(f"/api/v1/users/{zoe}", json={"display_name": "x"})).status_code == 403
