"""``marketplace.entitlements`` (T026): does a member own a product — read by 009 (widget products), 022
(themes), 017 (``product_owned`` unlocks) and Community cosmetics. Owning survives a failed activation
(the ownership is kept and retried); refunded, revoked and expired ownerships do not count."""

from typing import Any
from uuid import UUID

from sqlalchemy import Select, select

from portalab.capabilities.visuals import live_looks
from portalab.core.db import Database
from portalab.modules.marketplace.activation.service import USABLE
from portalab.modules.marketplace.models import Ownership, Product, ProductVersion


def waits_for(conditions: Any) -> dict[str, int]:
    """#99: what a locked item waits for — the highest level, the most Contribution its conditions ask."""
    out: dict[str, int] = {}
    for condition in conditions if isinstance(conditions, list) else []:
        if not isinstance(condition, dict):
            continue
        for kind, key, name in (
            ("min_level", "level", "level"),
            ("min_contribution", "contribution", "contribution"),
        ):
            value = condition.get(key) if condition.get("kind") == kind else None
            if isinstance(value, int):
                out[name] = max(out.get(name, 0), value)
    return out


class Entitlements:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def owns(self, user_id: UUID, product: str) -> bool:
        async with self.database.session() as session:
            found = await session.scalar(
                select(Ownership.id)
                .join(Product, Product.id == Ownership.product_id)
                .where(Ownership.user_id == user_id, Product.key == product, Ownership.state.in_(USABLE))
                .limit(1)
            )
        return found is not None

    async def owned_items(self, user_id: UUID, product_type: str) -> list[dict[str, Any]]:
        """#46: what a member owns of one type, to show on a profile — key, names (by language), icon,
        rarity and look (the product's current version)."""
        async with self.database.session() as session:
            rows = await session.execute(
                select(
                    Product.key, Product.icon, Product.rarity, ProductVersion.names, ProductVersion.payload
                )
                .join(Ownership, Ownership.product_id == Product.id)
                .join(
                    ProductVersion,
                    (ProductVersion.product_id == Product.id)
                    & (ProductVersion.version == Product.current_version),
                )
                .where(
                    Ownership.user_id == user_id, Product.type == product_type, Ownership.state.in_(USABLE)
                )
                .distinct()
                .order_by(Product.key)
            )
            return [
                {
                    "key": key,
                    "names": dict(names or {}),
                    "icon": icon or (payload or {}).get("icon"),
                    "rarity": rarity,
                    "style": (payload or {}).get("style"),
                }
                for key, icon, rarity, names, payload in rows
            ]

    async def owned_by_type(self, user_id: UUID, product_type: str) -> list[str]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(Product.key)
                .join(Ownership, Ownership.product_id == Product.id)
                .where(
                    Ownership.user_id == user_id, Product.type == product_type, Ownership.state.in_(USABLE)
                )
                .distinct()
            )
            return sorted(rows.scalars())


class ThemeEntitlementsReader:
    """``marketplace.theme_entitlements`` (027 US11): the theme keys sold by available ``theme`` products
    (their current version's ``payload.theme``) and the ones a member owns."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def _themes(self) -> Select[tuple[str]]:
        return (
            select(ProductVersion.payload["theme"].astext)
            .join(Product, Product.id == ProductVersion.product_id)
            .where(Product.type == "theme", ProductVersion.version == Product.current_version)
        )

    async def sold(self) -> frozenset[str]:
        async with self.database.session() as session:
            rows = await session.scalars(self._themes().where(Product.state == "available"))
            return frozenset(key for key in rows if key)

    async def owned(self, user_id: UUID) -> frozenset[str]:
        async with self.database.session() as session:
            rows = await session.scalars(
                self._themes()
                .join(Ownership, Ownership.product_id == Product.id)
                .where(Ownership.user_id == user_id, Ownership.state.in_(USABLE))
            )
            return frozenset(key for key in rows if key)


class CosmeticsReader:
    """``marketplace.cosmetics`` (027): any cosmetic choice sold through a product type whose current
    version names it in ``payload[field]`` — notification styles and animations — and the ones a member
    owns (directly, or through a pack)."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def _choices(self, kind: str, field: str) -> Select[tuple[str]]:
        return (
            select(ProductVersion.payload[field].astext)
            .join(Product, Product.id == ProductVersion.product_id)
            .where(Product.type == kind, ProductVersion.version == Product.current_version)
        )

    async def sold(self, kind: str, field: str) -> frozenset[str]:
        async with self.database.session() as session:
            # 027: an unavailable product (a reward of an achievement, out of sale) still keeps its design
            # for its owners
            rows = await session.scalars(
                self._choices(kind, field).where(Product.state.in_(("available", "unavailable")))
            )
            return frozenset(key for key in rows if key)

    async def owned(self, user_id: UUID, kind: str, field: str) -> frozenset[str]:
        async with self.database.session() as session:
            rows = await session.scalars(
                self._choices(kind, field)
                .join(Ownership, Ownership.product_id == Product.id)
                .where(Ownership.user_id == user_id, Ownership.state.in_(USABLE))
            )
            return frozenset(key for key in rows if key)

    async def waiting(self, user_id: UUID, kind: str, field: str) -> dict[str, dict[str, int]]:
        """#99: the choices a member won (a booster) but may not wear yet — their level, or Contribution, is
        not reached: what each one waits for (``{"level": 7}``), to show them locked with the reason; and
        (028) those whose visual pack is off (``{"unavailable": 1}``)."""
        async with self.database.session() as session:
            rows = await session.execute(
                self._choices(kind, field)
                .add_columns(Ownership.conditions_snapshot)
                .join(Ownership, Ownership.product_id == Product.id)
                .where(Ownership.user_id == user_id, Ownership.state == "locked")
            )
            out = {choice: waits_for(conditions) for choice, conditions in rows.all() if choice}
        # 028 (T081): what the member owns but its pack is switched off — kept, « currently unavailable »
        held = live_looks.held(kind)
        if held:
            for choice in (await self.owned(user_id, kind, field)) & held:
                out[choice] = {"unavailable": 1}
        return out

    async def details(self, kind: str, field: str) -> dict[str, dict[str, Any]]:
        """#71: for each choice sold, the product selling it: its key, rarity, price and names (030)."""
        async with self.database.session() as session:
            rows = await session.execute(
                select(
                    ProductVersion.payload[field].astext,
                    Product.key,
                    Product.rarity,
                    ProductVersion.price_coins,
                    ProductVersion.names,
                )
                .join(Product, Product.id == ProductVersion.product_id)
                .where(
                    Product.type == kind,
                    ProductVersion.version == Product.current_version,
                    Product.state.in_(("available", "unavailable")),
                )
            )
            return {
                choice: {"product": key, "rarity": rarity, "price": price, "names": dict(names or {})}
                for choice, key, rarity, price, names in rows
                if choice
            }

    async def equipped(self, user_id: UUID) -> dict[str, Any]:
        """027: the profile cosmetics a member wears (banner and frame keys, film backdrop)."""
        from portalab.modules.marketplace.looks.service import equipped_of

        return await equipped_of(self.database, user_id)
