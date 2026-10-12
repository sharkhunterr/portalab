"""015 T018 — catalog: categories, product types, detail with type/price/conditions/refund policy and the
viewer's ownership and named eligibility; availability states (archived hidden from new purchases, still
visible to owners); multilingual names; the ``product`` search provider (008 conformance)."""

import pytest
from httpx import AsyncClient

from portalab.capabilities.search.testkit import ProviderWorld, SearchProviderContractKit
from portalab.core.authz_port import Principal
from portalab.modules.marketplace.integrations import ProductSearchProvider
from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, published

pytestmark = pytest.mark.integration


async def test_catalog_and_detail(mk: MkHarness, client: AsyncClient) -> None:
    await mk.module.catalog.add_category("cosmetics", "marketplace:category.cosmetics", 1)
    await mk.module.catalog.create(
        mk.p("boss"),
        {
            "key": "night_owl",
            "type": "badge",
            "category": "cosmetics",
            "version": {
                "price_coins": 50,
                "conditions": [{"kind": "min_level", "level": 3}],
                "names": {"en": "Night owl", "fr": "Oiseau de nuit"},
                "payload": {"label": "Night owl"},
            },
        },
    )
    draft = await client.get("/api/v1/marketplace/products")  # anonymous
    assert draft.status_code == 401
    await login(client, "ursula")
    assert (await client.get("/api/v1/marketplace/products")).json() == []  # drafts are hidden
    await mk.module.catalog.move(mk.p("boss"), "night_owl", "available")
    await published(mk, "hourglass", "title", payload={"label": "Hourglass"})
    assert [c["key"] for c in (await client.get("/api/v1/marketplace/categories")).json()] == ["cosmetics"]
    listed = (await client.get("/api/v1/marketplace/products", params={"category": "cosmetics"})).json()
    assert [p["key"] for p in listed] == ["night_owl"]
    assert [
        p["key"] for p in (await client.get("/api/v1/marketplace/products", params={"q": "oiseau"})).json()
    ] == ["night_owl"]
    detail = (await client.get("/api/v1/marketplace/products/night_owl")).json()
    assert detail["names"] == {"en": "Night owl", "fr": "Oiseau de nuit"} and detail["price_coins"] == 50
    assert detail["refund_policy"] == {"refundable": True, "window_days": 7, "percent": 100}
    assert {(c["name"], c["met"], c["reason"]) for c in detail["eligibility"]} == {
        ("min_level", False, "unmet"),
        ("coins", False, "unmet"),
    }

    await mk.module.catalog.move(mk.p("boss"), "hourglass", "unavailable")
    assert [p["key"] for p in (await client.get("/api/v1/marketplace/products")).json()] == ["night_owl"]
    await mk.module.grants.grant(mk.p("boss"), mk.people["ursula"], "night_owl", "gift")
    await mk.module.catalog.move(mk.p("boss"), "night_owl", "archived")
    mine = (await client.get("/api/v1/marketplace/products/night_owl")).json()
    assert mine["state"] == "archived" and mine["owned"] is True  # owners keep it
    await login(client, "ulrich")
    assert (await client.get("/api/v1/marketplace/products/night_owl")).status_code == 404
    assert (await client.get("/api/v1/marketplace/products")).json() == []


@pytest.mark.integration
class TestProductProvider(SearchProviderContractKit):
    @pytest.fixture(autouse=True)
    def _harness(self, mk: MkHarness) -> None:
        self.mk = mk

    async def make_world(self) -> ProviderWorld:
        for key in ("star_badge", "star_title"):
            await published(self.mk, key, "badge", payload={"label": key})

        class OnlyFor:
            async def is_allowed(
                self, principal: Principal, permission: str, resource: object = None
            ) -> bool:
                return principal.user_id == allowed.user_id

        allowed = self.mk.p("ursula")
        provider = ProductSearchProvider(self.mk.module.catalog, OnlyFor())

        async def hide(key: str) -> None:
            await self.mk.module.catalog.move(self.mk.p("boss"), key, "unavailable")

        return ProviderWorld(provider, allowed, self.mk.p("ulrich"), "star", hide)


async def test_the_whole_catalogue_is_listed_past_five_hundred_products(mk: MkHarness) -> None:
    """#80, #91: the shop lists every product, never cut — past 500, then past 1000, the last ones by key (the
    themes, then the theme packs and the widgets) were silently dropped."""
    import inspect

    from portalab.modules.marketplace.products.service import Catalog

    assert inspect.signature(Catalog.listing).parameters["limit"].default is None


async def test_a_search_looks_through_every_product_before_limiting(mk: MkHarness) -> None:
    """#91: the text filter comes before the limit — a product far down the keys is still found."""
    for key in ("aardvark", "abacus", "abbey"):
        await published(mk, key)
    await published(mk, "zebra_crossing")
    found = await mk.module.catalog.listing(q="zebra", limit=2)
    assert [p.key for p, _ in found] == ["zebra_crossing"]
    assert len(await mk.module.catalog.listing(limit=2)) == 2
