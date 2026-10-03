"""``marketplace.entitlements`` (T026): does a member own a product — read by 009 (widget products), 022
(themes), 017 (``product_owned`` unlocks) and Community cosmetics. Owning survives a failed activation
(the ownership is kept and retried); refunded, revoked and expired ownerships do not count."""

from uuid import UUID

from sqlalchemy import select

from portalab.core.db import Database
from portalab.modules.marketplace.activation.service import LIVE
from portalab.modules.marketplace.models import Ownership, Product


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
