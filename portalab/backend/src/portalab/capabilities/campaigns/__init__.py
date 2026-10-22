"""Campaign contracts (spec 014, contracts/campaigns-contracts.md).

A *campaign* is a time-bound themed context (≠ a domain event, CD-009). The Campaigns module implements:
* ``economy.modifiers`` (013 ``ModifierProvider``) — factors with ``campaign:<key>:<version>:<modifier>``
  references for occurrences inside an activation interval; never amounts (combination is 013's CD-024);
* ``economy.definition_sources`` (013 ``DefinitionSource``) — campaign-scoped achievements while active;
* ``campaigns.reader`` (``CampaignReader``: 009 ``campaign_active`` widget condition, 017 unlocks);
* ``campaigns.content`` (``CampaignContentProvider``) and the 011 ``CalendarSource(kind="campaign")``;
* ``campaigns.discounts`` (``ShopDiscounts``, 027) — shop price reductions of the campaigns active at an
  instant, for the products or categories each one names; the Marketplace applies the best one.
Domain attributes for conditions come from ``activity.attributes`` providers (e.g. Media 024)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec
from portalab.capabilities.statistics import CAMPAIGNS as READER

CONTENT = "campaigns.content"
DISCOUNTS = "campaigns.discounts"


@dataclass(frozen=True, slots=True)
class CampaignRef:
    key: str
    name: str
    version: int
    started_at: datetime
    ends_at: datetime | None = None
    theme_key: str | None = None
    presentation_priority: int = 0


@dataclass(frozen=True, slots=True)
class ScopedDefinition:
    key: str
    campaign: str
    version: int
    definition: dict[str, Any] = field(default_factory=dict)
    active_from: datetime | None = None


@runtime_checkable
class CampaignReader(Protocol):
    async def is_active(self, campaign: str, at: datetime | None = None) -> bool: ...

    async def active_for_user(self, user: UUID, at: datetime | None = None) -> Sequence[CampaignRef]: ...


@runtime_checkable
class CampaignContentProvider(Protocol):
    async def achievements_active_at(self, at: datetime) -> Sequence[ScopedDefinition]: ...

    async def quests_active_at(self, at: datetime) -> Sequence[ScopedDefinition]: ...


@dataclass(frozen=True, slots=True)
class ShopDiscount:
    """``percent`` off the price of ``products`` (keys) and of every product in ``categories`` (keys)."""

    campaign: str
    name: str
    ref: str  # campaign:<key>:<version>:<discount id>
    percent: int
    products: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    ends_at: datetime | None = None
    names: dict[str, str] = field(default_factory=dict)
    seasons: tuple[str, ...] = ()  # every product of these seasons (« christmas »)

    def covers(self, product: str, category: str | None, season: str | None = None) -> bool:
        return (
            product in self.products
            or (category is not None and category in self.categories)
            or (season is not None and season in self.seasons)
        )


@runtime_checkable
class ShopDiscounts(Protocol):
    async def active_discounts(self, at: datetime) -> Sequence[ShopDiscount]: ...


def best_discount(
    discounts: Sequence[ShopDiscount], product: str, category: str | None, season: str | None = None
) -> ShopDiscount | None:
    """The largest reduction covering the product (discounts never add up)."""
    covering = [d for d in discounts if d.covers(product, category, season)]
    return max(covering, key=lambda d: (d.percent, d.ref)) if covering else None


def discounted(price: int, percent: int) -> int:
    """The reduced price, rounded up to a whole Coin (a reduction never makes a priced product free)."""
    if price <= 0 or percent <= 0:
        return price
    return max(1, -(-price * (100 - percent) // 100))


DISCOUNTS_SPEC = CapabilitySpec(
    name=DISCOUNTS,
    version="1.0",
    protocol=ShopDiscounts,
    multi_provider=False,
    description="Shop discounts of the campaigns active at an instant (Campaigns 014, 027)",
)
CONTENT_SPEC = CapabilitySpec(
    name=CONTENT,
    version="1.0",
    protocol=CampaignContentProvider,
    multi_provider=False,
    description="Campaign-scoped achievements and quests active at an instant (Campaigns 014)",
)
SPECS: tuple[CapabilitySpec, ...] = (CONTENT_SPEC, DISCOUNTS_SPEC)
__all__ = [
    "CONTENT",
    "DISCOUNTS",
    "READER",
    "CampaignContentProvider",
    "CampaignReader",
    "CampaignRef",
    "ScopedDefinition",
    "ShopDiscount",
    "ShopDiscounts",
    "best_discount",
    "discounted",
]
