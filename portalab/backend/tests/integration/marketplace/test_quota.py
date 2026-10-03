"""015 T031 — quota products: Coins spent through the ledger, units credited through 024's
``RequestQuotaService`` (Marketplace never consumes quota); a refund removes unused units and is refused
once some were used; product definitions cannot carry any priority; nothing in Media's request model can
order requests by purchase."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.media_core import QUOTA
from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import FakeQuota, MkHarness, published

pytestmark = pytest.mark.integration


async def test_quota_products(mk: MkHarness, client: AsyncClient) -> None:
    quota = FakeQuota()
    mk.module.capabilities.provide(QUOTA, quota, instance_ref="fake024", owner="module:test", priority=1)
    await published(
        mk,
        "requests_3",
        "quota",
        price_coins=30,
        payload={"kind": "media_requests", "units": 3},
        refund_policy={"refundable": True, "window_days": 7, "percent": 100},
    )
    await mk.coins("ursula", 100)
    await login(client, "ursula")
    first = (await client.post("/api/v1/marketplace/products/requests_3/acquire")).json()
    assert (
        first["state"] == "active"
        and quota.units[mk.people["ursula"]] == 3
        and await mk.balance("ursula") == 70
    )
    refunded = await client.post(
        f"/api/v1/me/marketplace/owned/{first['id']}/refund", json={"reason": "Unused"}
    )
    assert refunded.json()["state"] == "refunded" and quota.units[mk.people["ursula"]] == 0
    second = (await client.post("/api/v1/marketplace/products/requests_3/acquire")).json()
    quota.units[mk.people["ursula"]] -= 1  # Media consumed one unit
    used = await client.post(f"/api/v1/me/marketplace/owned/{second['id']}/refund", json={"reason": "x"})
    assert used.status_code == 409 and used.json()["code"] == "marketplace.not_refundable"

    async with mk.database.session() as session:
        columns = (
            (
                await session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema IN ('media', 'marketplace') AND table_name IN "
                        "('requests', 'ownerships', 'product_versions', 'request_quota_units')"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert not [c for c in columns if any(w in c for w in ("priority", "rank", "boost", "queue"))]
