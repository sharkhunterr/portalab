"""015 T029 — grants are marked ``origin=grant`` (optional expiry) and audited; revocation needs an
enumerated ground and a reason, removes access without rewriting history, notifies the member and refunds
a Coins purchase unless the ground is ``abuse``; every sensitive action is in the marketplace audit; only
the authorized roles may act."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.dashboard import ENTITLEMENTS
from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, confirmed, published

pytestmark = pytest.mark.integration


async def test_grants_revocations_audit(mk: MkHarness, client: AsyncClient) -> None:
    await published(mk, "owl", "badge", price_coins=40, payload={"label": "Owl"})
    await published(mk, "star", "badge", payload={"label": "Star"})
    await mk.coins("ursula", 100)
    bought = await mk.module.purchases.acquire(mk.p("ursula"), "owl", "k")
    ulrich = str(mk.people["ulrich"])

    await login(client, "ursula")
    for method, path, body in (
        ("POST", "/api/v1/admin/marketplace/grants", {"user_id": ulrich, "product": "star", "reason": "x"}),
        (
            "POST",
            f"/api/v1/admin/marketplace/ownerships/{bought.id}/revoke",
            {"ground": "abuse", "reason": "x"},
        ),
        ("POST", f"/api/v1/admin/marketplace/ownerships/{bought.id}/refund", {"reason": "x"}),
        ("GET", "/api/v1/admin/marketplace/audit", None),
        ("POST", "/api/v1/admin/marketplace/products/owl/archive", {}),
    ):
        assert (await client.request(method, path, json=body)).status_code == 403, path

    await login(client, "boss")
    expiring = (mk.clock.now() + timedelta(days=1)).isoformat()
    granted = await confirmed(
        client,
        "POST",
        "/api/v1/admin/marketplace/grants",
        {"user_id": ulrich, "product": "star", "reason": "Event winner", "expires_at": expiring},
    )
    assert (
        granted.status_code == 201
        and granted.json()["origin"] == "grant"
        and granted.json()["price_paid"] == 0
    )
    bad = await client.post(
        f"/api/v1/admin/marketplace/ownerships/{bought.id}/revoke", json={"ground": "boredom", "reason": "x"}
    )
    assert bad.status_code == 422
    revoked = await confirmed(
        client,
        "POST",
        f"/api/v1/admin/marketplace/ownerships/{bought.id}/revoke",
        {"ground": "withdrawn_for_cause", "reason": "Product withdrawn"},
    )
    assert revoked.json()["state"] == "revoked" and revoked.json()["revoke_ground"] == "withdrawn_for_cause"
    assert await mk.balance("ursula") == 100  # refunded: not abuse

    again = await mk.module.purchases.acquire(mk.p("ursula"), "owl", "k2")
    abuse = await confirmed(
        client,
        "POST",
        f"/api/v1/admin/marketplace/ownerships/{again.id}/revoke",
        {"ground": "abuse", "reason": "Fraud"},
    )
    assert abuse.json()["state"] == "revoked" and await mk.balance("ursula") == 60  # abuse: no refund

    [entitlements] = mk.module.capabilities.system_providers(ENTITLEMENTS)
    assert await entitlements.provider.owns(mk.people["ulrich"], "star")
    mk.clock.advance(timedelta(days=2))
    assert await mk.module.revocations.expire() == 1
    assert not await entitlements.provider.owns(mk.people["ulrich"], "star")

    await login(client, "boss")
    audit = (await client.get("/api/v1/admin/marketplace/audit", params={"limit": 50})).json()["items"]
    actions = {entry["action"] for entry in audit}
    assert {
        "marketplace.product_created",
        "marketplace.product_published",
        "marketplace.granted",
        "marketplace.revoked",
        "marketplace.refunded",
    } <= actions
    async with mk.database.session() as session:
        history = (
            (await session.execute(text("SELECT state FROM marketplace.ownerships ORDER BY acquired_at, id")))
            .scalars()
            .all()
        )
    assert sorted(history) == ["expired", "revoked", "revoked"]  # history kept, never rewritten
