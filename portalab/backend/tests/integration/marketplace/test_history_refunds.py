"""015 T027 — history lists price, snapshot and status; a refund within policy is a new ledger transaction
reversing the purchase (never an edit) and refunds the ownership; non-refundable products are labelled
before purchase and refused (``marketplace.not_refundable``); partial percentages; the window;
``marketplace.refund`` once."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, confirmed, published

pytestmark = pytest.mark.integration


async def test_refunds(mk: MkHarness, client: AsyncClient) -> None:
    await published(mk, "owl", "badge", price_coins=40, payload={"label": "Owl"})
    await published(
        mk, "half", "badge", price_coins=50, payload={"label": "Half"}, refund_policy={"percent": 50}
    )
    await published(mk, "plug", "plugin", price_coins=20, payload={"extension": "x"})
    await mk.coins("ursula", 200)
    await login(client, "ursula")
    plug_detail = (await client.get("/api/v1/marketplace/products/plug")).json()
    assert plug_detail["refund_policy"]["refundable"] is False  # labelled before purchase
    owl = (await client.post("/api/v1/marketplace/products/owl/acquire")).json()
    half = (await client.post("/api/v1/marketplace/products/half/acquire")).json()
    plug = (await client.post("/api/v1/marketplace/products/plug/acquire")).json()
    assert await mk.balance("ursula") == 90
    history = (await client.get("/api/v1/me/marketplace/purchases")).json()
    assert {(h["product_key"], h["price_paid"], h["product_version"]) for h in history} == {
        ("owl", 40, 1),
        ("half", 50, 1),
        ("plug", 20, 1),
    }
    assert next(h for h in history if h["product_key"] == "owl")["refundable_until"] is not None

    refused = await client.post(f"/api/v1/me/marketplace/owned/{plug['id']}/refund", json={"reason": "No"})
    assert refused.status_code == 409 and refused.json()["code"] == "marketplace.not_refundable"
    refunded = await client.post(
        f"/api/v1/me/marketplace/owned/{owl['id']}/refund", json={"reason": "Changed my mind"}
    )
    assert refunded.json()["state"] == "refunded" and await mk.balance("ursula") == 130
    assert (
        await client.post(f"/api/v1/me/marketplace/owned/{owl['id']}/refund", json={"reason": "x"})
    ).status_code == 409
    await client.post(f"/api/v1/me/marketplace/owned/{half['id']}/refund", json={"reason": "Half back"})
    assert await mk.balance("ursula") == 155  # 50 % of 50

    again = (await client.post("/api/v1/marketplace/products/owl/acquire")).json()
    mk.clock.advance(timedelta(days=8))
    await login(client, "ursula")  # the clock jump expired the session
    late = await client.post(f"/api/v1/me/marketplace/owned/{again['id']}/refund", json={"reason": "Late"})
    assert late.status_code == 409 and late.json()["code"] == "marketplace.not_refundable"
    await login(client, "boss")  # an administrator may refund outside the window (confirmed, audited)
    admin = await confirmed(
        client, "POST", f"/api/v1/admin/marketplace/ownerships/{again['id']}/refund", {"reason": "Goodwill"}
    )
    assert admin.json()["state"] == "refunded" and await mk.balance("ursula") == 155

    async with mk.database.session() as session:
        refunds = (
            await session.execute(
                text(
                    "SELECT kind, delta, reverses_transaction_id IS NOT NULL FROM gamification.transactions "
                    "WHERE kind = 'refund' ORDER BY seq"
                )
            )
        ).all()
    assert [tuple(r) for r in refunds] == [("refund", 40, True), ("refund", 25, True), ("refund", 40, True)]
    assert len(await mk.events("marketplace.refund")) == 3
