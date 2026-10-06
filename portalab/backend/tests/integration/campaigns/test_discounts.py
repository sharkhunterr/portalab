"""027 — a campaign's shop discounts apply only while it is active; the best reduction covering a product
(or its category) wins, discounts never add up, and a priced product never becomes free."""

import pytest

from portalab.capabilities.campaigns import DISCOUNTS, ShopDiscount, best_discount, discounted
from tests.integration.campaigns.conftest import HALLOWEEN, CampHarness, later, paris

pytestmark = pytest.mark.integration


def test_best_and_rounding() -> None:
    small = ShopDiscount("a", "A", "campaign:a:1:x", 10, products=("poster",))
    large = ShopDiscount("b", "B", "campaign:b:1:y", 20, categories=("themes",))
    assert best_discount([small, large], "poster", None) is small
    assert best_discount([small, large], "poster", "themes") is large
    assert best_discount([small, large], "other", None) is None
    assert [discounted(p, 20) for p in (100, 99, 1, 0)] == [80, 80, 1, 0]


async def test_active_only(cm: CampHarness) -> None:
    definition = {
        **HALLOWEEN,
        "discounts": [
            {"id": "spooky", "percent": 20, "products": ["pumpkin_theme"], "categories": ["themes"]}
        ],
    }
    await cm.create(definition=definition)
    provider = cm.ev.full.identity.capabilities.system_providers(DISCOUNTS)[0].provider
    assert await provider.active_discounts(paris(10, 19)) == []
    await cm.at(later(paris(10, 20, 0), minutes=1))
    [found] = await provider.active_discounts(paris(10, 21))
    assert (found.campaign, found.percent, found.products, found.categories) == (
        "halloween",
        20,
        ("pumpkin_theme",),
        ("themes",),
    )
    assert found.ref == "campaign:halloween:1:spooky"
