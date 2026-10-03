"""015 T019 — publishing, price, condition and refund-policy changes create new versions (history never
reinterpreted: an ownership keeps its snapshot); they are sensitive — confirmed and audited; a new product
type extends the catalog without a schema change; priority-like settings are rejected."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.marketplace import ActivationResult, OwnershipView, ProductType
from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, confirmed, product_def

pytestmark = pytest.mark.integration


class Sticker:
    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        return ActivationResult("active")

    async def deactivate(self, ownership: OwnershipView) -> None:
        return None


async def test_versions_confirmation_audit(mk: MkHarness, client: AsyncClient) -> None:
    await login(client, "ursula")
    assert (
        await client.post("/api/v1/admin/marketplace/products", json={"definition": product_def("x")})
    ).status_code == 403
    await login(client, "boss")
    created = await client.post(
        "/api/v1/admin/marketplace/products", json={"definition": product_def("owl", price_coins=30)}
    )
    assert created.status_code == 201 and created.json()["state"] == "draft"
    publish = await client.post("/api/v1/admin/marketplace/products/owl/publish", json={})
    assert publish.status_code == 409 and publish.json()["code"] == "authz.confirmation_required"
    assert (await confirmed(client, "POST", "/api/v1/admin/marketplace/products/owl/publish", {})).json()[
        "state"
    ] == "available"

    await mk.coins("ulrich", 100)
    owned = await mk.module.purchases.acquire(mk.p("ulrich"), "owl", "k1")
    revised = await confirmed(
        client,
        "PUT",
        "/api/v1/admin/marketplace/products/owl",
        {"definition": {"names": {"en": "Owl"}, "price_coins": 80, "payload": {"label": "Owl"}}},
    )
    assert revised.json()["version"] == 2 and revised.json()["price_coins"] == 80
    async with mk.database.session() as session:
        snapshot = (
            await session.execute(
                text("SELECT product_version, price_paid FROM marketplace.ownerships WHERE id = :i"),
                {"i": owned.id},
            )
        ).one()
        versions = (
            await session.execute(
                text("SELECT version, price_coins FROM marketplace.product_versions ORDER BY version")
            )
        ).all()
        audited = (
            (
                await session.execute(
                    text(
                        "SELECT action FROM audit.audit_entries "
                        "WHERE action LIKE 'marketplace.product%' ORDER BY seq"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert tuple(snapshot) == (1, 30) and [tuple(v) for v in versions] == [(1, 30), (2, 80)]
    assert audited == [
        "marketplace.product_created",
        "marketplace.product_published",
        "marketplace.product_revised",
    ]
    async with mk.database.session() as session:
        with pytest.raises(Exception, match="append-only"):
            await session.execute(text("UPDATE marketplace.product_versions SET price_coins = 1"))

    mk.module.product_types.register(
        ProductType("sticker", "module:test", Sticker(), payload_fields=("shape",))
    )
    sticker = await client.post(
        "/api/v1/admin/marketplace/products",
        json={
            "definition": {
                "key": "heart",
                "type": "sticker",
                "version": {"names": {"en": "Heart"}, "payload": {"shape": "heart"}},
            }
        },
    )
    assert sticker.status_code == 201
    for payload in ({"shape": "x", "queue_priority": 1}, {"boost": True}, {"rank_bonus": 2}):
        bad = await client.post(
            "/api/v1/admin/marketplace/products",
            json={
                "definition": {
                    "key": "bad",
                    "type": "sticker",
                    "version": {"names": {"en": "Bad"}, "payload": payload},
                }
            },
        )
        assert bad.status_code == 422 and bad.json()["code"] == "marketplace.priority_forbidden", payload
    unknown = await client.post(
        "/api/v1/admin/marketplace/products",
        json={
            "definition": {
                "key": "bad",
                "type": "sticker",
                "version": {"names": {"en": "Bad"}, "payload": {"color": 1}},
            }
        },
    )
    assert unknown.status_code == 422 and unknown.json()["code"] == "marketplace.invalid_product"
