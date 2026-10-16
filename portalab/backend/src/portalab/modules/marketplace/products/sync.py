"""A product described as data — the demo catalog's entries and, issue 1, the elements of imported
visual packs — brought into the catalog: created and put on sale when new, revised when its price, texts,
contents or level changed (purchases keep their snapshot), then its presentation and availability (copies,
purchase limit) follow the description. A booster's odds stay the administrators' once it exists."""

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.core.authz_port import Principal
from portalab.modules.marketplace.models import Ownership, Product
from portalab.modules.marketplace.products.definition import AvailabilityIn, PresentationIn
from portalab.modules.marketplace.products.service import Catalog, ProductNotFound

# an entry's fields: key, type, price, rarity, names, descriptions, payload, collection, icon, featured,
# level, supply, limit, repeatable, reward_only, contribution, config_required, season
Entry = Mapping[str, Any]


def definition(product: Entry) -> dict[str, Any]:
    """The catalog definition of an entry (what ``Catalog.create``/``revise`` take)."""
    version: dict[str, Any] = {
        "price_coins": product["price"],
        "names": product["names"],
        "descriptions": product["descriptions"],
        "payload": product["payload"],
        "conditions": [
            *([{"kind": "min_level", "level": product["level"]}] if product.get("level") else []),
            *(
                [{"kind": "min_contribution", "contribution": product["contribution"]}]
                if product.get("contribution")
                else []
            ),
        ],
        **({"config_required": True} if product.get("config_required") else {}),
    }
    return {
        "key": product["key"],
        "type": product["type"],
        **({"repeatable": True} if product.get("repeatable") else {}),
        "version": version,
    }


async def sync_product(catalog: Catalog, actor: Principal, product: Entry, *, resume: bool = False) -> str:
    """Brings one entry into the catalog: ``created``, ``revised`` or ``unchanged``; ``resume`` puts an
    entry taken off sale back on it (an imported element enabled again — never the demo catalog's)."""
    raw = definition(product)
    outcome = "unchanged"
    try:
        current, version = await catalog.get(product["key"])
    except ProductNotFound:
        await catalog.create(actor, raw)
        await catalog.move(actor, product["key"], "available")
        current, version = await catalog.get(product["key"])
        outcome = "created"
    if outcome != "created" and product.get("keep_existing"):
        # 028: one of Portalab's own products — once it exists, it is the administrators' (prices, texts,
        # availability); a release never writes over it, it is only put back on sale
        if resume and current.state == "unavailable":
            await catalog.move(actor, product["key"], "available")
        return outcome
    if outcome != "created" and product["type"] == "booster":
        pass  # #81: its odds and refunds are the administrators' — never written back over them
    elif product.get("reward_only"):  # 027: given by an achievement, never sold
        if current.state == "available":
            await catalog.move(actor, product["key"], "unavailable")
    elif outcome != "created":
        wanted = raw["version"]
        stored = {
            "price_coins": version.price_coins,
            "names": dict(version.names),
            "descriptions": dict(version.descriptions),
            "payload": dict(version.payload),
            "conditions": list(version.conditions),
        }
        if stored != wanted:
            await catalog.revise(actor, product["key"], wanted)
            outcome = "revised"
        if resume and current.state == "unavailable":  # issue 1: an element put back on sale
            await catalog.move(actor, product["key"], "available")
    current, _ = await catalog.get(product["key"])
    presentation = PresentationIn(
        rarity=product["rarity"],
        poster_effect="none",
        featured=bool(product.get("featured")),
        icon=product.get("icon"),
        season=product.get("season"),
    )
    if (current.rarity, current.poster_effect, current.featured, current.icon, current.season) != (
        presentation.rarity,
        presentation.poster_effect,
        presentation.featured,
        presentation.icon,
        presentation.season,
    ) or current.category_id is None:
        await catalog.present(actor, product["key"], presentation, product.get("collection"))
    limit = product.get("limit") or (None, None)
    if (current.supply, current.limit_count, current.limit_days) != (product.get("supply"), *limit):
        await catalog.set_availability(
            actor,
            product["key"],
            AvailabilityIn(supply=product.get("supply"), limit_count=limit[0], limit_days=limit[1]),
            product.get("level"),
            product.get("contribution"),  # #59: never drop the contribution minimum
        )
    return outcome


# an ownership a member still has (a refunded, revoked or expired one is not)
LIVE_OWNERSHIP = ("active", "needs_configuration", "activation_failed", "locked")


class MarketplaceCatalogWriter:
    """028 (``marketplace.catalog_writer``): the elements of visual packs published through the same path."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    async def publish(self, actor: Principal, product: Entry) -> str:
        return await sync_product(self.catalog, actor, product, resume=bool(product.get("resume", True)))

    async def withdraw(self, actor: Principal, key: str) -> bool:
        try:
            current, _ = await self.catalog.get(key)
        except ProductNotFound:
            return False
        if current.state == "available":
            await self.catalog.move(actor, key, "unavailable")
            return True
        return False

    async def existing(self, keys: Iterable[str]) -> frozenset[str]:
        wanted = list(keys)
        if not wanted:
            return frozenset()
        async with self.catalog.database.session() as session:
            rows = await session.scalars(select(Product.key).where(Product.key.in_(wanted)))
            return frozenset(rows)

    async def owners(self, keys: Iterable[str]) -> int:
        wanted = list(keys)
        if not wanted:
            return 0
        async with self.catalog.database.session() as session:
            count = await session.scalar(
                select(func.count(Ownership.id))
                .join(Product, Product.id == Ownership.product_id)
                .where(Product.key.in_(wanted), Ownership.state.in_(LIVE_OWNERSHIP))
            )
        return int(count or 0)

    async def retire(self, actor: Principal, key: str) -> None:
        """Off sale for good: archived (the catalog keeps its versions and its purchases' history)."""
        try:
            current, _ = await self.catalog.get(key)
        except ProductNotFound:
            return
        if current.state != "archived":
            await self.catalog.move(actor, key, "archived")
