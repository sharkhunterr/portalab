"""021 T037 — privacy center: inventory of the datum classes held about me (owner, classification, level,
lock, retention) with export/deletion links; my preference change is kept under an admin override."""

import httpx
from fastapi import FastAPI

from portalab.modules.privacy.policies.service import PolicyRequest
from tests.authz_fixtures import user
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform


async def test_inventory_and_preference(app: FastAPI, client: httpx.AsyncClient, full: FullPlatform) -> None:
    owner = await create_user(module_of(app), "owner")
    await login(client, "owner")
    inventory = (await client.get("/api/v1/me/privacy")).json()
    assert inventory["export_endpoint"] == "/api/v1/me/export"
    entry = next(item for item in inventory["data"] if item["datum_class"] == "profile_field")
    assert entry["owner"] == "module:identity" and entry["classification"] == "personal"
    assert (
        entry["effective_level"] == "private"
        and entry["locked_by_policy"] is False
        and entry["user_choosable"]
    )

    missing = await client.put(
        "/api/v1/me/privacy/visibility/profile_field", json={"level": "public", "datum_ref": "bio"}
    )
    assert missing.status_code == 404  # no such field yet
    await client.patch("/api/v1/me/profile", json={"fields": {"bio": {"value": "hi"}}})
    ok = await client.put(
        "/api/v1/me/privacy/visibility/profile_field", json={"level": "public", "datum_ref": "bio"}
    )
    assert ok.json() == {"stored": True, "effective_now": True}

    await full.privacy.policies.apply(
        user(owner), PolicyRequest("profile_field", "force_private", "moderation", subject_user_id=owner)
    )
    locked = next(
        item
        for item in (await client.get("/api/v1/me/privacy")).json()["data"]
        if item["datum_class"] == "profile_field"
    )
    assert locked["locked_by_policy"] is True and locked["effective_level"] == "private"
    unknown = await client.put("/api/v1/me/privacy/visibility/nope", json={"level": "public"})
    assert unknown.status_code == 404
