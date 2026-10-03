"""015 T034 — no real money anywhere: no payment/currency/card fields in the schema or the API, Coins come
only from earning (no route sells Coins), money-like endpoints are idempotent and amounts are bounded
integers."""

import re

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, published

pytestmark = pytest.mark.integration
MONEY = re.compile(
    r"(payment|currency|card|iban|stripe|paypal|invoice|checkout|euro|dollar|fiat)", re.IGNORECASE
)


def test_api_has_no_payment_surface() -> None:
    from portalab.app.main import create_app

    schema = create_app(static_dir=None).openapi()
    paths = [
        p
        for p in schema["paths"]
        if p.startswith(
            ("/api/v1/marketplace", "/api/v1/me/marketplace", "/api/v1/admin/marketplace", "/api/v1/projects")
        )
    ]
    assert paths and not [p for p in paths if MONEY.search(p)]
    names = [n for n in schema["components"]["schemas"] if n.startswith(("Marketplace", "Project"))]
    fields = [f for n in names for f in schema["components"]["schemas"][n].get("properties", {})]
    assert not [f for f in fields if MONEY.search(f)]
    assert not [p for p in schema["paths"] if re.search(r"/coins/(buy|purchase)", p)]


async def test_schema_and_bounds(mk: MkHarness, client: AsyncClient) -> None:
    async with mk.database.session() as session:
        columns = (
            (
                await session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'marketplace'"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert not [c for c in columns if MONEY.search(c)]
    await published(mk, "owl", "badge", price_coins=10, payload={"label": "Owl"})
    await login(client, "boss")
    for price in (0, -5, 1.5, 10**9):
        response = await client.post(
            "/api/v1/admin/marketplace/products",
            json={
                "definition": {
                    "key": "p",
                    "type": "badge",
                    "version": {"names": {"en": "P"}, "price_coins": price},
                }
            },
        )
        assert response.status_code == 422, price
    await mk.coins("ursula", 20)
    await login(client, "ursula")
    for _ in range(3):
        await client.post("/api/v1/marketplace/products/owl/acquire", headers={"Idempotency-Key": "same"})
    assert await mk.balance("ursula") == 10
    fund = await client.post(
        "/api/v1/projects/00000000-0000-7000-8000-000000000000/fund",
        json={"amount": 2.5, "acknowledged": True},
    )
    assert fund.status_code == 422
