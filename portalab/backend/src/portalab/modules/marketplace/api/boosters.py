"""#81: boosters (products of type ``booster``) — those on sale with what each holds, the odds and what a
duplicate gives back, and the sealed ones I keep; opening one (``marketplace.purchase``,
``Idempotency-Key``): its price charged (or a sealed one used), the looks granted, the duplicates' Coins
given back, the items to keep put in the reserve; the boosters I opened; my reserve and using one of its
items."""

from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Path, Query
from pydantic import BaseModel, Field
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
from portalab.modules.marketplace.boosters import booster_info
from portalab.modules.marketplace.models import Product, ProductVersion
from portalab.modules.marketplace.pricing import active_discounts
from portalab.modules.marketplace.products.service import ProductNotFound

router = APIRouter(prefix="/api/v1", tags=["marketplace-boosters"])

KEY = Path(pattern=r"^[a-z0-9_]{1,96}$")


def _booster_out(
    module: Module, product: Product, version: ProductVersion, opened: int = 0, sealed: int = 0
) -> dict[str, Any]:
    info = booster_info(
        product.key, version.names, version.price_coins, version.payload or {}, module.openings.today()
    )
    per_member = info["per_member"]
    return {
        "key": product.key,
        "names": dict(version.names),
        "descriptions": dict(version.descriptions),
        "price": version.price_coins or 0,
        "rarity": product.rarity,
        **info,
        "theme": info["look"],
        "on_sale": product.state == "available" and module.openings.sold(product, version),
        "left": None if per_member is None else max(0, per_member - opened),
        # sealed ones I keep (offered — a level reward, an achievement — or bought): opened for free
        "sealed": sealed,
    }


async def _boosters(module: Module, user: UUID) -> list[dict[str, Any]]:
    opened = await module.openings.opened(user)
    sealed = await module.openings.sealed(user)
    shown = {p.key: (p, v) for p, v, _ in await module.openings.boosters()}
    # an offered booster stays openable out of its season
    for key in set(sealed) - set(shown):
        try:
            shown[key] = await module.catalog.get(key)
        except ProductNotFound:
            continue
    return [_booster_out(module, p, v, opened.get(p.key, 0), sealed.get(p.key, 0)) for p, v in shown.values()]


@router.get("/marketplace/boosters")
async def boosters(principal: Reader, module: Module) -> list[dict[str, Any]]:
    """#81: the boosters on sale now — how many cards, the odds per rarity, the rarity guaranteed, what a
    duplicate gives back, until when a season's is on sale, how many openings I have left and the sealed
    ones I keep."""
    return await _boosters(module, _me(principal))


@router.post("/marketplace/boosters/{key}/open", status_code=201)
async def open_booster(
    principal: Buyer,
    module: Module,
    key: Annotated[str, KEY],
    sealed: Annotated[bool, Query()] = False,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)] = None,
) -> dict[str, Any]:
    """#81: open a booster — bought now (its price charged), or ``sealed``: one I keep in my reserve
    (offered, or bought earlier). A look I did not own is mine (held, not usable yet, below its level or
    Contribution), one I owned is a duplicate whose Coins come back at once, an item to keep goes to my
    reserve."""
    user = _me(principal)
    opening, drawn = await module.openings.open(
        principal, key, idempotency_key or str(uuid4()), sealed=sealed
    )
    keys = await category_keys(module)
    discounts = await active_discounts(module.capabilities, utc_now(module.clock))
    mine = {b["key"]: b for b in await _boosters(module, user)}
    booster = mine.get(opening.booster_key)
    if booster is None:  # out of its season, its last offered one just opened: as it is now
        product, version = await module.catalog.get(opening.booster_key)
        opened = await module.openings.opened(user)
        booster = _booster_out(module, product, version, opened.get(product.key, 0), 0)
    return {
        "booster": booster,
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
                    locked=card.locked,
                ).model_dump(),
                "outcome": card.outcome,
                "duplicate": card.outcome == "duplicate",
                "refund": card.refund,
                "locked": card.locked,
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
    keys = {str(card["product"]) for row in rows for card in row.drawn} | {row.booster_key for row in rows}
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
            "names": names.get(row.booster_key, {}),
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
                    "locked": bool(card.get("locked")),
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
            # a sealed booster: opened, not used
            "booster": product.type == "booster",
            # #131: a level pass: used on an item waiting for its level
            "early_unlock": product.type == "early_unlock",
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


class EarlyUnlockIn(BaseModel):
    target: Annotated[str, Field(min_length=1, max_length=96)]


@router.post("/marketplace/reserve/{key}/unlock", status_code=201)
async def unlock_early(
    principal: Buyer, module: Module, key: Annotated[str, KEY], body: EarlyUnlockIn
) -> dict[str, Any]:
    """#131: spend a level pass of my reserve on an item I hold but may not wear yet — usable at once."""
    row = await module.openings.unlock_early(principal, key, body.target)
    return {"ownership": str(row.id), "product": body.target, "state": row.state}
