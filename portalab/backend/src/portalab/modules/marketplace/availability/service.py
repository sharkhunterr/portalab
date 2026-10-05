"""Scarcity (027): a product exists in a limited number of copies — its own ``supply`` or, by default, the
supply of its rarity (common: unlimited, legendary: a couple, set by the administrators) — and a member may
buy a repeatable product only so many times in a period. Copies in circulation are the live ownerships
(refunded or revoked ones go back to the shop). Checked under the product's row lock at acquisition,
reported as named conditions on the product page. Scarcity never buys any priority."""

from collections.abc import Iterable, Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.activation.service import LIVE
from portalab.modules.marketplace.eligibility.service import Check
from portalab.modules.marketplace.models import Ownership, Product, ProductVersion, Rarity

RARITIES = ("common", "rare", "epic", "legendary")


class SoldOut(Conflict):
    default_code = "marketplace.sold_out"
    default_title = "Sold out"


class PurchaseLimit(Conflict):
    default_code = "marketplace.purchase_limit"
    default_title = "Purchase limit reached"


class Availability:
    def __init__(self, database: Database, audit: AuditSink, *, clock: Clock | None = None) -> None:
        self.database = database
        self.audit = audit
        self.clock = clock

    # --- rarities ------------------------------------------------------------------------------------
    async def rarities(self) -> dict[str, int | None]:
        async with self.database.session() as session:
            rows = {r.key: r.supply for r in (await session.execute(select(Rarity))).scalars()}
        return {key: rows.get(key) for key in RARITIES}

    async def set_rarities(self, actor: Principal, values: Mapping[str, int | None]) -> dict[str, int | None]:
        unknown = sorted(set(values) - set(RARITIES))
        if unknown or any(v is not None and not 1 <= v <= 1_000_000 for v in values.values()):
            raise ValidationFailed("Unknown rarity or invalid supply.", code="marketplace.invalid_rarity")
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            for key, supply in values.items():
                row = await uow.session.get(Rarity, key)
                if row is None:
                    uow.session.add(Rarity(key=key, supply=supply, updated_at=now))
                else:
                    row.supply, row.updated_at = supply, now
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="marketplace.rarities_changed",
                    actor=actor,
                    resource=ResourceRef("marketplace", "rarities"),
                    decision="allow",
                    context={"supply": dict(values)},
                    sensitive=True,
                ),
            )
        return await self.rarities()

    # --- copies --------------------------------------------------------------------------------------
    @staticmethod
    def supply_of(product: Product, rarities: Mapping[str, int | None]) -> int | None:
        return product.supply if product.supply is not None else rarities.get(product.rarity)

    async def in_circulation(
        self, product_ids: Iterable[UUID], session: AsyncSession | None = None
    ) -> dict[UUID, int]:
        ids = list(product_ids)
        if not ids:
            return {}
        statement = (
            select(Ownership.product_id, func.count())
            .where(Ownership.product_id.in_(ids), Ownership.state.in_(LIVE))
            .group_by(Ownership.product_id)
        )
        if session is not None:
            rows = (await session.execute(statement)).all()
        else:
            async with self.database.session() as own:
                rows = (await own.execute(statement)).all()
        return {product_id: int(count) for product_id, count in rows}

    async def stock(self, products: Iterable[Product]) -> dict[UUID, tuple[int | None, int | None]]:
        """``{product id: (supply, remaining)}`` — both ``None`` when unlimited."""
        items = list(products)
        rarities = await self.rarities()
        used = await self.in_circulation(p.id for p in items)
        out: dict[UUID, tuple[int | None, int | None]] = {}
        for product in items:
            supply = self.supply_of(product, rarities)
            out[product.id] = (supply, None if supply is None else max(0, supply - used.get(product.id, 0)))
        return out

    async def bought_recently(self, user: UUID, product: Product, session: AsyncSession | None = None) -> int:
        if not product.limit_count or not product.limit_days:
            return 0
        since = utc_now(self.clock) - timedelta(days=product.limit_days)
        statement = select(func.count()).where(
            Ownership.user_id == user,
            Ownership.product_id == product.id,
            Ownership.origin == "purchase",
            Ownership.acquired_at >= since,
        )
        if session is not None:
            return int(await session.scalar(statement) or 0)
        async with self.database.session() as own:
            return int(await own.scalar(statement) or 0)

    async def checks(self, user: UUID, product: Product) -> list[Check]:
        """Named conditions for the product page: copies left, purchases left in the period."""
        out: list[Check] = []
        supply, remaining = (await self.stock([product]))[product.id]
        if supply is not None and remaining is not None:
            out.append(Check("stock", remaining, remaining > 0, "" if remaining > 0 else "unmet"))
        if product.limit_count and product.limit_days:
            used = await self.bought_recently(user, product)
            ok = used < product.limit_count
            out.append(
                Check(
                    "purchase_limit", f"{used}/{product.limit_count}", ok, "" if ok else "unmet"
                )
            )
        return out

    async def guard(
        self, session: AsyncSession, user: UUID, product: Product, version: ProductVersion
    ) -> None:
        """Inside the acquisition's unit of work, under the product row lock."""
        await session.execute(select(Product.id).where(Product.id == product.id).with_for_update())
        rarities = await self.rarities()
        supply = self.supply_of(product, rarities)
        if supply is not None:
            used = (await self.in_circulation([product.id], session)).get(product.id, 0)
            if used >= supply:
                raise SoldOut("Every copy of this product is taken.", extensions={"supply": supply})
        if (
            product.limit_count
            and product.limit_days
            and await self.bought_recently(user, product, session) >= product.limit_count
        ):
            raise PurchaseLimit(
                "You reached the purchase limit for this period.",
                extensions={"count": product.limit_count, "days": product.limit_days},
            )
        if product.type == "bundle":
            await self._guard_pack(session, user, version.payload or {}, rarities)

    async def _guard_pack(
        self,
        session: AsyncSession,
        user: UUID,
        payload: Mapping[str, Any],
        rarities: Mapping[str, int | None],
    ) -> None:
        keys = [str(k) for k in payload.get("products") or []]
        if not keys:
            return
        inner = list((await session.execute(select(Product).where(Product.key.in_(keys)))).scalars())
        owned = set(
            (
                await session.execute(
                    select(Ownership.product_id).where(
                        Ownership.user_id == user,
                        Ownership.product_id.in_([p.id for p in inner]),
                        Ownership.state.in_(LIVE),
                    )
                )
            ).scalars()
        )
        used = await self.in_circulation([p.id for p in inner], session)
        gone = [
            p.key
            for p in inner
            if p.id not in owned
            and (supply := self.supply_of(p, rarities)) is not None
            and used.get(p.id, 0) >= supply
        ]
        if gone:
            raise SoldOut("A product of this pack is sold out.", extensions={"products": gone})
