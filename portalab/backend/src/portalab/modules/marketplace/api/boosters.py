"""#81: boosters in the shop — those on sale with what each holds, the odds and what a duplicate gives
back; opening one (``marketplace.purchase``, ``Idempotency-Key``): its price charged, the looks granted,
the duplicates' Coins given back, the items to keep put in the reserve; the boosters I opened; my reserve
and using one of its items."""

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Header, Path, Query
from sqlalchemy import select

from portalab.core.time import utc_now
from portalab.modules.marketplace.api.catalog import (
    Buyer,
    Reader,
    _me,
    category_keys,
    product_out,
)
from portalab.modules.marketplace.api.projects import Module
from portalab.modules.marketplace.boosters import (
    BOOSTERS,
    RARITIES,
    RESERVE_TYPES,
    Booster,
    odds_percent,
    refund_of,
    until,
)
from portalab.modules.marketplace.models import Product, ProductVersion
from portalab.modules.marketplace.pricing import active_discounts

router = APIRouter(prefix="/api/v1", tags=["marketplace-boosters"])

KEY = Path(pattern=r"^[a-z0-9_]{1,96}$")


def _booster_out(module: Module, booster: Booster, opened: int = 0) -> dict[str, Any]:
    end = until(booster, module.openings.today())
    return {
        "key": booster.key,
        "names": dict(booster.names),
        "descriptions": dict(booster.descriptions),
        "price": booster.price,
        "cards": booster.cards,
        "odds": odds_percent(booster),
        "guarantee": booster.guarantee,
        "refunds": {rarity: refund_of(booster, rarity) for rarity in RARITIES},
        "theme": booster.theme,
        # what comes out of it: looks for the collection, or items for the reserve
        "kind": "reserve" if booster.types <= RESERVE_TYPES else "looks",
        "until": end.isoformat() if end else None,
        "per_member": booster.per_member,
        "left": None if booster.per_member is None else max(0, booster.per_member - opened),
    }


@router.get("/marketplace/boosters")
async def boosters(principal: Reader, module: Module) -> list[dict[str, Any]]:
    """#81: the boosters on sale now — how many cards, the odds per rarity, the rarity guaranteed, what a
    duplicate gives back, until when a season's is on sale and how many openings I have left."""
    opened = await module.openings.opened(_me(principal))
    return [_booster_out(module, b, opened.get(b.key, 0)) for b in module.openings.on_sale()]


@router.post("/marketplace/boosters/{key}/open", status_code=201)
async def open_booster(
    principal: Buyer,
    module: Module,
    key: Annotated[str, KEY],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)] = None,
) -> dict[str, Any]:
    """#81: open a booster — its price charged, its cards drawn now: a look I did not own is mine, one I
    owned is a duplicate whose Coins come back at once, an item to keep goes to my reserve."""
    opening, drawn = await module.openings.open(principal, key, idempotency_key or str(uuid4()))
    keys = await category_keys(module)
    discounts = await active_discounts(module.capabilities, utc_now(module.clock))
    booster = BOOSTERS[opening.booster_key]
    opened = await module.openings.opened(_me(principal))
    return {
        "booster": _booster_out(module, booster, opened.get(booster.key, 0)),
        "opening": {
            "id": str(opening.id),
            "opened_at": opening.opened_at.isoformat(),
            "price": opening.price,
            "refund": opening.refund,
        },
        "cards": [
            {
                "product": product_out(
                    card.product,
                    card.version,
                    card.outcome != "reserve",
                    categories=keys,
                    discounts=discounts,
                ).model_dump(),
                "outcome": card.outcome,
                "duplicate": card.outcome == "duplicate",
                "refund": card.refund,
            }
            for card in drawn
        ],
    }


@router.get("/marketplace/boosters/openings")
async def openings(
    principal: Reader, module: Module, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> list[dict[str, Any]]:
    """#81: the boosters I opened, the latest first — what each cost, what came out, what came back."""
    rows = await module.openings.history(_me(principal), limit)
    keys = {str(card["product"]) for row in rows for card in row.drawn}
    async with module.database.session() as session:
        found = await session.execute(
            select(Product.key, ProductVersion.names)
            .join(
                ProductVersion,
                (ProductVersion.product_id == Product.id)
                & (ProductVersion.version == Product.current_version),
            )
            .where(Product.key.in_(keys))
        )
        names = {key: dict(value) for key, value in found.all()}
    return [
        {
            "id": str(row.id),
            "booster": row.booster_key,
            "names": dict(BOOSTERS[row.booster_key].names) if row.booster_key in BOOSTERS else {},
            "opened_at": row.opened_at.isoformat(),
            "price": row.price,
            "refund": row.refund,
            "cards": [
                {
                    "product": card["product"],
                    "names": names.get(str(card["product"]), {}),
                    "rarity": card.get("rarity"),
                    "outcome": card.get("outcome"),
                    "refund": card.get("refund", 0),
                }
                for card in row.drawn
            ],
        }
        for row in rows
    ]


@router.get("/marketplace/reserve")
async def reserve(principal: Reader, module: Module) -> list[dict[str, Any]]:
    """#81: the items I keep to use when I want — requests, freezes, boosts, rescues, tickets."""
    items = await module.openings.reserve(_me(principal))
    keys = await category_keys(module)
    discounts = await active_discounts(module.capabilities, utc_now(module.clock))
    return [
        {
            "product": product_out(
                product, version, False, categories=keys, discounts=discounts
            ).model_dump(),
            "quantity": quantity,
            "needs_configuration": version.config_required,
        }
        for product, version, quantity in items
    ]


@router.post("/marketplace/reserve/{key}/use", status_code=201)
async def use(
    principal: Buyer,
    module: Module,
    key: Annotated[str, KEY],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)] = None,
) -> dict[str, Any]:
    """#81: use one item of my reserve — it is granted and takes effect as if bought (a ticket then waits
    for its form in « My purchases »)."""
    row = await module.openings.use(principal, key, idempotency_key or str(uuid4()))
    return {"ownership": str(row.id), "product": key, "state": row.state}
