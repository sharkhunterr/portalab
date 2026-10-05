"""027 — scarcity: a product exists in as many copies as its rarity allows (set by the administrators,
overridable per product); a refunded or revoked copy goes back to the shop; a repeatable product may be
bought only so many times per period; a minimum level is a named condition (changing it makes a version);
a pack is refused when one of its products is sold out."""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from portalab.modules.marketplace.availability.service import PurchaseLimit, SoldOut
from portalab.modules.marketplace.products.definition import AvailabilityIn
from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, product_def

pytestmark = pytest.mark.integration


async def _create(mk: MkHarness, key: str, kind: str = "badge", **extra: object) -> None:
    await mk.module.catalog.create(mk.p("boss"), {**product_def(key, kind), **extra})
    await mk.module.catalog.move(mk.p("boss"), key, "available")


async def test_supply_follows_rarity_and_returns_on_revoke(mk: MkHarness, client: AsyncClient) -> None:
    boss = mk.p("boss")
    assert (await mk.module.availability.set_rarities(boss, {"legendary": 2, "common": None}))[
        "legendary"
    ] == 2
    await _create(mk, "crown", presentation={"rarity": "legendary"})
    await _create(mk, "pebble")  # common: unlimited
    for name in ("ursula", "ulrich"):
        await mk.module.purchases.acquire(mk.p(name), "crown", f"k-{name}")
    with pytest.raises(SoldOut):
        await mk.module.purchases.acquire(mk.p("vera"), "crown", "k-vera")

    await login(client, "vera")
    listed = {p["key"]: p for p in (await client.get("/api/v1/marketplace/products")).json()}
    assert (listed["crown"]["supply"], listed["crown"]["remaining"]) == (2, 0)
    assert (listed["pebble"]["supply"], listed["pebble"]["remaining"]) == (None, None)
    detail = (await client.get("/api/v1/marketplace/products/crown")).json()
    assert ("stock", 0, False) in {(c["name"], c["value"], c["met"]) for c in detail["eligibility"]}

    owned = await mk.module.entitlements.owned_by_type(mk.people["ursula"], "badge")  # type: ignore[arg-type]
    assert "crown" in owned
    from sqlalchemy import select

    from portalab.modules.marketplace.models import Ownership, Product

    async with mk.database.session() as session:
        crown = await session.scalar(select(Product).where(Product.key == "crown"))
        assert crown is not None
        ownership = await session.scalar(
            select(Ownership).where(
                Ownership.product_id == crown.id, Ownership.user_id == mk.people["ursula"]
            )
        )
    assert ownership is not None
    await mk.module.revocations.revoke(boss, ownership.id, "withdrawn_for_cause", "test")
    await mk.module.purchases.acquire(mk.p("vera"), "crown", "k-vera-2")  # the copy came back

    await mk.module.catalog.set_availability(boss, "crown", AvailabilityIn(supply=5), None)
    detail = (await client.get("/api/v1/marketplace/products/crown")).json()
    assert (detail["supply"], detail["remaining"]) == (5, 3)  # a product overrides its rarity


async def test_purchase_limit_per_period_and_min_level(mk: MkHarness) -> None:
    await _create(
        mk,
        "requests",
        "quota",
        repeatable=True,
        availability={"limit_count": 2, "limit_days": 30},
    )
    ursula = mk.p("ursula")
    await mk.module.purchases.acquire(ursula, "requests", "a")
    await mk.module.purchases.acquire(ursula, "requests", "b")
    with pytest.raises(PurchaseLimit):
        await mk.module.purchases.acquire(ursula, "requests", "c")
    mk.clock.advance(timedelta(days=31))
    await mk.module.purchases.acquire(ursula, "requests", "d")  # a new period

    _, version = await mk.module.catalog.get("requests")
    await mk.module.catalog.set_availability(
        mk.p("boss"), "requests", AvailabilityIn(limit_count=2, limit_days=30), 10
    )
    _, revised = await mk.module.catalog.get("requests")
    assert revised.version == version.version + 1
    assert {"kind": "min_level", "level": 10} in revised.conditions
    await mk.module.catalog.set_availability(  # same level: no new version
        mk.p("boss"), "requests", AvailabilityIn(limit_count=2, limit_days=30), 10
    )
    assert (await mk.module.catalog.get("requests"))[1].version == revised.version


async def test_pack_refused_when_a_product_is_sold_out(mk: MkHarness) -> None:
    await _create(mk, "solo", availability={"supply": 1})
    await _create(mk, "duo")
    await _create(mk, "pack", "bundle")
    await mk.module.catalog.revise(
        mk.p("boss"), "pack", {"names": {"en": "Pack"}, "payload": {"products": ["solo", "duo"]}}
    )
    await mk.module.purchases.acquire(mk.p("ulrich"), "solo", "s")
    with pytest.raises(SoldOut):
        await mk.module.purchases.acquire(mk.p("ursula"), "pack", "p")
    # the one who already owns the sold-out product may still buy the pack
    assert (await mk.module.purchases.acquire(mk.p("ulrich"), "pack", "p2")).state == "active"
