"""``marketplace.entitlements`` (T026): does a member own a product — read by 009 (widget products), 022
(themes), 017 (``product_owned`` unlocks) and Community cosmetics. Owning survives a failed activation
(the ownership is kept and retried); refunded, revoked and expired ownerships do not count."""

from typing import Any
from uuid import UUID

from sqlalchemy import Select, select

from portalab.core.db import Database
from portalab.modules.marketplace.activation.service import LIVE
from portalab.modules.marketplace.models import Ownership, Product, ProductVersion


class Entitlements:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def owns(self, user_id: UUID, product: str) -> bool:
        async with self.database.session() as session:
            found = await session.scalar(
                select(Ownership.id)
                .join(Product, Product.id == Ownership.product_id)
                .where(Ownership.user_id == user_id, Product.key == product, Ownership.state.in_(LIVE))
                .limit(1)
            )
        return found is not None

    async def owned_by_type(self, user_id: UUID, product_type: str) -> list[str]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(Product.key)
                .join(Ownership, Ownership.product_id == Product.id)
                .where(Ownership.user_id == user_id, Product.type == product_type, Ownership.state.in_(LIVE))
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
                .where(Ownership.user_id == user_id, Ownership.state.in_(LIVE))
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
                .where(Ownership.user_id == user_id, Ownership.state.in_(LIVE))
            )
            return frozenset(key for key in rows if key)

    async def equipped(self, user_id: UUID) -> dict[str, Any]:
        """027: the profile cosmetics a member wears (banner and frame keys, film backdrop)."""
        from portalab.modules.marketplace.looks.service import equipped_of

        return await equipped_of(self.database, user_id)
