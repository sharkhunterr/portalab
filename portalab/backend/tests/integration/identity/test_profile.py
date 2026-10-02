"""002 T036 — display-name conflict ⇒ ``user.display_name_taken``; field visibility *preference* stored and
applied (default not-public); avatar replacement leaves no reachable old blob."""

import io

import httpx
import pytest
from fastapi import FastAPI
from PIL import Image
from sqlalchemy import select

from portalab.core.jobs.models import Job
from portalab.modules.identity.models import Profile, ProfileField
from portalab.modules.identity.services.profile import collect_avatar_blob
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration


def _png(color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
async def users(app: FastAPI) -> dict[str, str]:
    module = module_of(app)
    return {name: str(await create_user(module, name)) for name in ("alice", "bob")}


async def test_display_name_rename_and_conflict(client: httpx.AsyncClient, users: dict[str, str]) -> None:
    await login(client, "alice")
    renamed = await client.patch("/api/v1/me/profile", json={"display_name": "Alice Wonder"})
    assert renamed.status_code == 200 and renamed.json()["display_name"] == "Alice Wonder"
    clash = await client.patch("/api/v1/me/profile", json={"display_name": "BOB"})
    assert clash.status_code == 409
    assert clash.json()["code"] == "user.display_name_taken"
    invalid = await client.patch("/api/v1/me/profile", json={"display_name": "x"})
    assert invalid.status_code == 422 and invalid.json()["code"] == "user.display_name_invalid"


async def test_field_visibility_preferences(
    app: FastAPI, client: httpx.AsyncClient, users: dict[str, str]
) -> None:
    await login(client, "alice")
    response = await client.patch(
        "/api/v1/me/profile",
        json={
            "fields": {
                "bio": {"value": "Hello", "visibility": "public"},
                "city": {"value": "Lyon", "visibility": "community"},
                "score_note": {"value": "top", "visibility": "leaderboard"},
                "phone_note": {"value": "secret"},  # no visibility given ⇒ private
            }
        },
    )
    assert response.status_code == 200
    own = {field["key"]: field["visibility"] for field in response.json()["fields"]}
    assert own == {"bio": "public", "city": "community", "phone_note": "private", "score_note": "leaderboard"}

    other = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://portal.test")
    async with other:
        await login(other, "bob")
        seen = (await other.get(f"/api/v1/users/{users['alice']}/profile")).json()
    assert {field["key"] for field in seen["fields"]} == {"bio", "city"}

    removed = await client.patch("/api/v1/me/profile", json={"fields": {"bio": {"value": None}}})
    assert "bio" not in {field["key"] for field in removed.json()["fields"]}
    async with module_of(app).ctx.database.session() as session:
        stored = (await session.execute(select(ProfileField.key))).scalars().all()
    assert set(stored) == {"city", "phone_note", "score_note"}


async def test_avatar_replace_and_remove_leave_no_reachable_blob(
    app: FastAPI, client: httpx.AsyncClient, users: dict[str, str]
) -> None:
    module = module_of(app)
    await login(client, "alice")
    first = await client.put(
        "/api/v1/me/avatar", content=_png((255, 0, 0)), headers={"Content-Type": "image/png"}
    )
    assert first.status_code == 204
    async with module.ctx.database.session() as session:
        first_key = (await session.get(Profile, users["alice"])).avatar_blob_key  # type: ignore[union-attr]
    assert first_key and await module.ctx.blobs.exists(first_key)
    served = await client.get(f"/api/v1/users/{users['alice']}/avatar")
    assert served.status_code == 200 and served.headers["content-type"] == "image/png"

    second = await client.put(
        "/api/v1/me/avatar", content=_png((0, 0, 255)), headers={"Content-Type": "image/png"}
    )
    assert second.status_code == 204
    async with module.ctx.database.session() as session:
        jobs = (await session.execute(select(Job.kind, Job.payload))).all()
    assert [(kind, payload["blob"]) for kind, payload in jobs] == [("identity.avatar_blob_gc", first_key)]
    assert await collect_avatar_blob(module.ctx, first_key) is True
    assert not await module.ctx.blobs.exists(first_key)

    removed = await client.delete("/api/v1/me/avatar")
    assert removed.status_code == 204
    assert (await client.get(f"/api/v1/users/{users['alice']}/avatar")).status_code == 404


async def test_invalid_avatar_keeps_the_old_one(
    app: FastAPI, client: httpx.AsyncClient, users: dict[str, str]
) -> None:
    await login(client, "alice")
    await client.put("/api/v1/me/avatar", content=_png((1, 2, 3)), headers={"Content-Type": "image/png"})
    bad = await client.put("/api/v1/me/avatar", content=b"garbage", headers={"Content-Type": "image/png"})
    assert bad.status_code == 422 and bad.json()["code"] == "user.avatar_invalid"
    assert (await client.get(f"/api/v1/users/{users['alice']}/avatar")).status_code == 200


async def test_shared_blob_is_not_collected_while_referenced(app: FastAPI, users: dict[str, str]) -> None:
    module = module_of(app)
    for name in ("alice", "bob"):
        http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://portal.test")
        async with http:
            await login(http, name)
            await http.put(
                "/api/v1/me/avatar", content=_png((9, 9, 9)), headers={"Content-Type": "image/png"}
            )
    async with module.ctx.database.session() as session:
        keys = set((await session.execute(select(Profile.avatar_blob_key))).scalars())
    (key,) = keys  # identical images share one content-addressed blob
    assert await collect_avatar_blob(module.ctx, key) is False
    assert await module.ctx.blobs.exists(key)
