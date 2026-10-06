"""Prices (027): a product's price **now** — its Coins price less the best reduction of the campaigns
active at that instant (``campaigns.discounts``) for the product or its category. Without the Campaigns
module, or when it fails, the price is the catalog price (a failure never blocks a purchase)."""

from collections.abc import Sequence
from datetime import datetime

from portalab.capabilities.campaigns import DISCOUNTS, ShopDiscount, best_discount, discounted
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.marketplace.observability import log


async def active_discounts(capabilities: CapabilityRegistry, at: datetime) -> Sequence[ShopDiscount]:
    try:
        providers = capabilities.system_providers(DISCOUNTS)
        if not providers:
            return []
        return list(await providers[0].provider.active_discounts(at))
    except Exception:
        log.warning("campaign discounts unavailable")
        return []


def price_now(
    discounts: Sequence[ShopDiscount], product: str, category: str | None, price: int | None
) -> tuple[int | None, ShopDiscount | None]:
    if not price:
        return price, None
    discount = best_discount(discounts, product, category)
    return (discounted(price, discount.percent), discount) if discount else (price, None)
