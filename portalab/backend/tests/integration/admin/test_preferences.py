"""020 T014/T010 — /me/preferences: user-overridable keys only, bounded by policy, ``locked`` reported; the
user value is retained under a lock and effective again when the policy is removed; erasure removes it."""

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from tests.authz_fixtures import make_admin
from tests.integration.admin.settings_fixture import test_settings  # noqa: F401 — fixture
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform

pytestmark = pytest.mark.usefixtures("test_settings")


def _pref(body: dict, key: str) -> dict:  # type: ignore[type-arg]
    return next(item for item in body["preferences"] if item["key"] == key)


async def test_preferences_and_policies(app: FastAPI, client: httpx.AsyncClient, full: FullPlatform) -> None:
    user_id = await create_user(module_of(app), "member")
    admin_id = await create_user(module_of(app), "boss")
    await make_admin(full, admin_id)
    await login(client, "member")
    listing = (await client.get("/api/v1/me/preferences")).json()
    keys = {item["key"] for item in listing["preferences"]}
    assert (
        {"demo.theme", "demo.pageSize"} <= keys
        and "demo.apiToken" not in keys
        and "identity.dormancyDays" not in keys
    )

    updated = (
        await client.put("/api/v1/me/preferences", json={"demo.theme": "dark", "demo.pageSize": 80})
    ).json()
    assert (
        _pref(updated, "demo.theme")["value"] == "dark" and _pref(updated, "demo.theme")["source"] == "user"
    )
    refused = await client.put("/api/v1/me/preferences", json={"identity.dormancyDays": 1})
    assert refused.status_code == 409 and refused.json()["code"] == "admin.not_a_preference"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as boss:
        await login(boss, "boss")
        lock = (await boss.post("/api/v1/admin/policies", json={"key": "demo.theme", "mode": "lock"})).json()
        bound = await boss.post(
            "/api/v1/admin/policies", json={"key": "demo.pageSize", "mode": "bound", "bounds": {"max": 50}}
        )
        assert bound.status_code == 201
        stacked = await boss.post("/api/v1/admin/policies", json={"key": "demo.theme", "mode": "lock"})
        assert stacked.status_code == 409

        locked = (await client.get("/api/v1/me/preferences")).json()
        theme = _pref(locked, "demo.theme")
        assert (
            theme["locked"]
            and theme["value"] == "auto"
            and theme["user_value"] == "dark"
            and theme["user_value_retained"]
        )
        page = _pref(locked, "demo.pageSize")
        assert page["value"] == 20 and page["user_value_retained"]  # 80 is outside the bound
        too_big = await client.put("/api/v1/me/preferences", json={"demo.pageSize": 99})
        assert too_big.status_code == 422 and too_big.json()["code"] == "admin.out_of_bounds"

        assert (await boss.delete(f"/api/v1/admin/policies/{lock['id']}")).status_code == 204
    restored = _pref((await client.get("/api/v1/me/preferences")).json(), "demo.theme")
    assert restored["value"] == "dark" and not restored["locked"]

    exporter = next(
        r.provider
        for r in full.identity.capabilities.system_providers(EXPORT_CAPABILITY)
        if r.instance_ref == "administration.preferences"
    )
    assert {rec.data["setting"] for rec in await exporter.export(user_id)} == {"demo.theme", "demo.pageSize"}
    eraser = next(
        r.provider
        for r in full.identity.capabilities.system_providers(ERASURE_CAPABILITY)
        if r.instance_ref == "administration.preferences"
    )
    await eraser.erase(user_id, "final")
    assert (await full.administration.config.get("demo.theme", user_id=user_id)).value == "auto"


async def test_concurrent_first_writes_do_not_collide(
    app: FastAPI, client: httpx.AsyncClient, full: FullPlatform
) -> None:
    """027 T094: two first writes of the same preference at once (e.g. a double click) both succeed."""
    import asyncio

    await create_user(module_of(app), "racer")
    await login(client, "racer")
    responses = await asyncio.gather(
        *(client.put("/api/v1/me/preferences", json={"demo.pageSize": 30 + n}) for n in range(4))
    )
    assert [r.status_code for r in responses] == [200] * 4
    final = _pref((await client.get("/api/v1/me/preferences")).json(), "demo.pageSize")
    assert final["source"] == "user" and final["value"] in {30, 31, 32, 33}
