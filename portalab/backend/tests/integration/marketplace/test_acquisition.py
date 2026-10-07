"""015 T023 — atomic acquisition: a fault after the spend leaves neither a spend nor an ownership; an
``Idempotency-Key`` replay returns the same ownership; concurrent double acquisitions yield one; a
permanent product cannot be owned twice while ``repeatable`` ones can; the snapshot (price paid, version,
conditions) is stored; Coins only move through the ledger; owners of an archived product keep it."""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, published

pytestmark = pytest.mark.integration


async def spends(mk: MkHarness, name: str) -> int:
    async with mk.database.session() as session:
        return int(
            await session.scalar(
                text("SELECT count(*) FROM gamification.transactions WHERE user_id = :u AND kind = 'spend'"),
                {"u": mk.people[name]},
            )
            or 0
        )


async def test_atomic_idempotent_acquisition(mk: MkHarness, client: AsyncClient) -> None:
    await published(mk, "owl", "badge", price_coins=40, payload={"label": "Owl"})
    await published(mk, "boost_pack", "badge", price_coins=10, payload={"label": "Pack"})
    await mk.coins("ursula", 100)

    async def boom() -> None:
        raise RuntimeError("crash after the spend")

    mk.module.purchases.after_spend = boom
    with pytest.raises(RuntimeError):
        await mk.module.purchases.acquire(mk.p("ursula"), "owl", "k0")
    mk.module.purchases.after_spend = None
    assert await mk.balance("ursula") == 100 and await spends(mk, "ursula") == 0  # no orphan spend

    await login(client, "ursula")
    path = "/api/v1/marketplace/products/owl/acquire"
    first = await client.post(path, headers={"Idempotency-Key": "a1"})
    replay = await client.post(path, headers={"Idempotency-Key": "a1"})
    assert first.status_code == 201 and replay.json()["id"] == first.json()["id"]
    assert first.json()["state"] == "active" and first.json()["price_paid"] == 40
    again = await client.post(path, headers={"Idempotency-Key": "a2"})
    assert again.status_code == 409 and again.json()["code"] == "marketplace.already_owned"
    assert await mk.balance("ursula") == 60 and await spends(mk, "ursula") == 1

    results = await asyncio.gather(
        *(mk.module.purchases.acquire(mk.p("ursula"), "boost_pack", f"c{i}") for i in range(3)),
        return_exceptions=True,
    )
    assert len([r for r in results if not isinstance(r, BaseException)]) == 1
    assert await mk.balance("ursula") == 50

    await mk.coins("ulrich", 5)
    await login(client, "ulrich")
    poor = await client.post(path)
    assert poor.status_code == 409 and poor.json()["code"] == "marketplace.insufficient_coins"
    async with mk.database.session() as session:
        await session.execute(
            text("UPDATE marketplace.products SET repeatable = true WHERE key = 'boost_pack'")
        )
        await session.commit()
    await mk.coins("ulrich", 100)
    for key in ("r1", "r2"):
        assert (
            await client.post(
                "/api/v1/marketplace/products/boost_pack/acquire", headers={"Idempotency-Key": key}
            )
        ).status_code == 201

    await mk.module.catalog.move(mk.p("boss"), "owl", "archived")
    await login(client, "ursula")
    owned = (await client.get("/api/v1/me/marketplace/owned")).json()
    assert {o["product_key"] for o in owned} == {"owl", "boost_pack"}
    assert (await client.post(path)).json()["code"] == "marketplace.not_available"
    assert len(await mk.events("marketplace.purchase")) == 4


class _Discounts:
    def __init__(self, percent: int) -> None:
        self.percent = percent

    async def active_discounts(self, at: object) -> list[object]:
        from portalab.capabilities.campaigns import ShopDiscount

        return [
            ShopDiscount("halloween", "Halloween", "campaign:halloween:1:x", self.percent, products=("owl",))
        ]


async def test_campaign_discount_is_charged(mk: MkHarness, client: AsyncClient) -> None:
    """027: an active campaign's reduction is shown on the product and charged at purchase."""
    from portalab.capabilities.campaigns import DISCOUNTS

    mk.ev.full.identity.capabilities.provide(DISCOUNTS, _Discounts(20), instance_ref="test", owner="test")
    await published(mk, "owl", "badge", price_coins=45, payload={"label": "Owl"})
    await published(mk, "plain", "badge", price_coins=10, payload={"label": "Plain"})
    await mk.coins("ursula", 100)
    await login(client, "ursula")
    shown = {p["key"]: p for p in (await client.get("/api/v1/marketplace/products")).json()}
    assert shown["owl"]["price_now"] == 36 and shown["owl"]["discount"]["percent"] == 20
    assert shown["plain"]["price_now"] == 10 and shown["plain"]["discount"] is None
    bought = await client.post("/api/v1/marketplace/products/owl/acquire", headers={"Idempotency-Key": "d1"})
    assert bought.status_code == 201 and bought.json()["price_paid"] == 36
    assert await mk.balance("ursula") == 64


async def test_purchase_notice_names_the_product(mk: MkHarness) -> None:
    """027: the owner is told the product's name in their language — never its technical key."""
    from typing import Any

    from portalab.capabilities.notifications import NOTIFY

    class _Outbox:
        def __init__(self) -> None:
            self.sent: list[Any] = []

        async def send(self, request: Any, **_: Any) -> Any:
            self.sent.append(request)
            return None

    outbox = _Outbox()
    mk.module.capabilities.provide(NOTIFY, outbox, instance_ref="t", owner="test")
    await published(mk, "widget_countdown", "badge", price_coins=10, payload={"label": "Countdown"})
    await mk.coins("ursula", 50)
    await mk.module.purchases.acquire(mk.p("ursula"), "widget_countdown", "n1")
    [notice] = [r for r in outbox.sent if r.category == "marketplace.purchase"]
    assert notice.params["product"] == "Widget Countdown"  # the English name, not « widget_countdown »
