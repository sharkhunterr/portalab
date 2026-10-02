"""021 T009/T011 — a high-permission viewer (even the Admin) cannot read another user's Private field; the
filter is applied after ``require()``; class defaults apply without a preference; never public by default."""

import httpx
from fastapi import FastAPI

from portalab.core.authz_port import Principal
from portalab.core.visibility_port import Redacted
from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.privacy_fixtures import FullPlatform


async def _profile_with_fields(app: FastAPI, client: httpx.AsyncClient) -> str:
    owner = await create_user(module_of(app), "owner")
    await login(client, "owner")
    await client.patch(
        "/api/v1/me/profile",
        json={
            "fields": {
                "bio": {"value": "public bio", "visibility": "public"},
                "city": {"value": "Lyon", "visibility": "community"},
                "rank_note": {"value": "top 10", "visibility": "leaderboard"},
                "phone_note": {"value": "secret", "visibility": "private"},
            }
        },
    )
    return str(owner)


async def test_admin_cannot_see_private_fields(
    app: FastAPI, client: httpx.AsyncClient, full: FullPlatform
) -> None:
    owner = await _profile_with_fields(app, client)
    admin_id = await create_user(module_of(app), "boss")
    await make_admin(full, admin_id)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as boss:
        await login(boss, "boss")
        seen = (await boss.get(f"/api/v1/users/{owner}/profile")).json()
    assert {field["key"] for field in seen["fields"]} == {"bio", "city"}
    own = (await client.get(f"/api/v1/users/{owner}/profile")).json()
    assert {field["key"] for field in own["fields"]} == {"bio", "city", "rank_note", "phone_note"}


async def test_filter_surfaces_and_defaults(
    full: FullPlatform, app: FastAPI, client: httpx.AsyncClient
) -> None:
    owner = await _profile_with_fields(app, client)
    from uuid import UUID, uuid4

    subject = UUID(owner)
    member, outsider = Principal(user_id=uuid4()), Principal()
    filter_ = full.privacy.filter
    assert await filter_.filter(member, subject, "profile_field", "rank_note", "x", "leaderboard") == "x"
    assert isinstance(await filter_.filter(member, subject, "profile_field", "rank_note", "x"), Redacted)
    assert isinstance(await filter_.filter(outsider, subject, "profile_field", "city", "x"), Redacted)
    assert await filter_.filter(outsider, subject, "profile_field", "bio", "x") == "x"
    # no preference recorded ⇒ class default (private), never public
    assert await full.privacy.visibility.effective_level(subject, "profile_field", "unknown") == "private"
    assert await full.privacy.visibility.effective_level(subject, "not_registered", None) == "private"
