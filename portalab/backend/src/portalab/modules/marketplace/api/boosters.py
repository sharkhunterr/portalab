"""#81 (proof of concept): boosters in the shop — what one holds and the odds, and a reveal (visual only:
nothing is charged, granted or refunded)."""

from typing import Annotated, Any

from fastapi import APIRouter, Path

from portalab.core.time import utc_now
from portalab.modules.marketplace.api.catalog import (
    Reader,
    _me,
    category_keys,
    owned_ids,
    product_out,
)
from portalab.modules.marketplace.api.projects import Module
from portalab.modules.marketplace.boosters import BOOSTERS, Booster, draw, odds_percent, refund_of
from portalab.modules.marketplace.pricing import active_discounts
from portalab.modules.marketplace.products.service import ProductNotFound

router = APIRouter(prefix="/api/v1", tags=["marketplace-boosters"])


def _booster_out(booster: Booster) -> dict[str, Any]:
    return {
        "key": booster.key,
        "names": dict(booster.names),
        "descriptions": dict(booster.descriptions),
        "price": booster.price,
        "cards": booster.cards,
        "odds": odds_percent(booster),
        "guarantee": booster.guarantee,
        "theme": booster.theme,
    }


@router.get("/marketplace/boosters")
async def boosters(_: Reader) -> list[dict[str, Any]]:
    """#81: the boosters on sale — how many cards, the odds per rarity, the rarity guaranteed."""
    return [_booster_out(b) for b in BOOSTERS.values()]


@router.post("/marketplace/boosters/{key}/reveal")
async def reveal(
    principal: Reader,
    module: Module,
    key: Annotated[str, Path(pattern=r"^[a-z0-9_]{1,64}$")],
) -> dict[str, Any]:
    """#81 (proof of concept): open a booster — its cards drawn now, each saying whether I own it already
    (a duplicate, refunded in Coins). Visual only: nothing is charged, granted or refunded yet."""
    booster = BOOSTERS.get(key)
    if booster is None:
        raise ProductNotFound("This booster does not exist.")
    mine = await owned_ids(module, _me(principal))
    rows = [
        (product, version)
        for product, version in await module.catalog.listing(owned_ids=mine)
        if product.type in booster.types and version.price_coins
    ]
    picked = draw(booster, rows, lambda row: row[0].rarity, lambda row: row[0].key)
    keys = await category_keys(module)
    discounts = await active_discounts(module.capabilities, utc_now(module.clock))
    cards = []
    for product, version in picked:
        owned = product.id in mine and not product.repeatable
        cards.append(
            {
                "product": product_out(
                    product, version, owned, categories=keys, discounts=discounts
                ).model_dump(),
                "duplicate": owned,
                "refund": refund_of(version.price_coins) if owned else 0,
            }
        )
    return {"booster": _booster_out(booster), "cards": cards, "preview": True}
