"""027 T088 — shop presentation: rarity, featured, poster effect, icon and collection are set at creation or
later without a new price version; the shop lists them; invalid values are refused; members cannot edit."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, published

pytestmark = pytest.mark.integration


async def test_presentation(mk: MkHarness, client: AsyncClient) -> None:
    await published(mk, "owl", "badge", price_coins=10)
    await login(client, "boss")
    made = await client.post(
        "/api/v1/admin/marketplace/categories",
        json={"key": "halloween", "label_key": "Halloween", "icon": "moon"},
    )
    assert made.status_code == 201, made.text
    body = {
        "presentation": {"rarity": "legendary", "featured": True, "poster_effect": "glitch", "icon": "moon"},
        "category": "halloween",
    }
    saved = await client.put("/api/v1/admin/marketplace/products/owl/presentation", json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["rarity"] == "legendary" and saved.json()["version"] == 1  # no new price version
    bad = await client.put(
        "/api/v1/admin/marketplace/products/owl/presentation",
        json={"presentation": {"rarity": "mythic"}, "category": None},
    )
    assert bad.status_code == 422
    unknown = await client.put(
        "/api/v1/admin/marketplace/products/owl/presentation", json={**body, "category": "nope"}
    )
    assert unknown.status_code == 422

    await login(client, "ursula")
    assert (
        await client.put("/api/v1/admin/marketplace/products/owl/presentation", json=body)
    ).status_code == 403
    listed = {p["key"]: p for p in (await client.get("/api/v1/marketplace/products")).json()}
    owl = listed["owl"]
    assert (owl["rarity"], owl["featured"], owl["poster_effect"], owl["icon"], owl["category"]) == (
        "legendary",
        True,
        "glitch",
        "moon",
        "halloween",
    )
    collections = (await client.get("/api/v1/marketplace/categories")).json()
    assert {"key": "halloween", "label_key": "Halloween", "icon": "moon"} in collections
    async with mk.database.session() as session:
        versions = await session.scalar(text("SELECT count(*) FROM marketplace.product_versions"))
    assert versions == 1


async def test_presentation_at_creation(mk: MkHarness, client: AsyncClient) -> None:
    await login(client, "boss")
    created = await client.post(
        "/api/v1/admin/marketplace/products",
        json={
            "definition": {
                "key": "ghost",
                "type": "badge",
                "presentation": {"rarity": "epic", "poster_effect": "neon"},
                "version": {"names": {"en": "Ghost"}, "price_coins": 5, "payload": {"label": "Ghost"}},
            }
        },
    )
    assert created.status_code == 201, created.text
    assert (created.json()["rarity"], created.json()["poster_effect"], created.json()["featured"]) == (
        "epic",
        "neon",
        False,
    )
