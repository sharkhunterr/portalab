"""``campaigns.discounts`` (027): the shop reductions of the campaigns active at an instant, in the version
in force — the Marketplace shows them and charges the reduced price (the best one when several apply)."""

from collections.abc import Sequence
from datetime import datetime

from portalab.capabilities.campaigns import ShopDiscount
from portalab.modules.campaigns.resolver.active import ActiveResolver


class CampaignDiscounts:
    def __init__(self, resolver: ActiveResolver) -> None:
        self.resolver = resolver

    async def active_discounts(self, at: datetime) -> Sequence[ShopDiscount]:
        out: list[ShopDiscount] = []
        for campaign in await self.resolver.at(at):
            for discount in campaign.definition.discounts:
                out.append(
                    ShopDiscount(
                        campaign=campaign.key,
                        name=campaign.definition.name(),
                        ref=f"campaign:{campaign.key}:{campaign.version}:{discount.id}",
                        percent=discount.percent,
                        products=tuple(discount.products),
                        categories=tuple(discount.categories),
                        ends_at=campaign.ends_at,
                        names=dict(campaign.definition.names),
                    )
                )
        return out
