"""Catalog (T020, T021; R7, FR-001..009): categories, products of a registered type, and **append-only
versions** — publishing, price, condition or refund-policy changes create a new version, so a purchase's
snapshot is never reinterpreted. States ``draft → available ⇄ unavailable → archived``; an archived
product is hidden from new purchases but stays with its owners. Every change is audited (sensitive)."""

from collections.abc import Callable
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.marketplace import ProductTypeRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.models import Category, Product, ProductVersion
from portalab.modules.marketplace.products.definition import (
    AvailabilityIn,
    PresentationIn,
    ProductVersionIn,
    check_payload,
    parse_product,
    parse_version,
)

State = Literal["draft", "available", "unavailable", "archived"]
MOVES: dict[str, frozenset[str]] = {
    "draft": frozenset({"available", "archived"}),
    "available": frozenset({"unavailable", "archived"}),
    "unavailable": frozenset({"available", "archived"}),
    "archived": frozenset(),
}


class ProductNotFound(NotFound):
    default_code = "marketplace.product_not_found"
    default_title = "Product not found"


def actor_id(actor: Principal) -> UUID | None:
    return actor.acting_for or actor.user_id


class Catalog:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        types: ProductTypeRegistry,
        config: Callable[[], Any],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.types = types
        self.config = config
        self.clock = clock

    async def _audit(
        self, session: AsyncSession, actor: Principal, action: str, product: Product, **context: Any
    ) -> None:
        await self.audit.record(
            session,
            AuditRecord(
                action=f"marketplace.{action}",
                actor=actor,
                resource=ResourceRef("product", product.key),
                decision="allow",
                context={"version": product.current_version, **context},
                sensitive=True,
            ),
        )

    def _policy(self, product_type: str, version: ProductVersionIn) -> dict[str, Any]:
        if version.refund_policy is not None:
            return version.refund_policy.model_dump()
        configured = self.config().refund_defaults.get(product_type)
        if isinstance(configured, dict):
            return {"refundable": True, "window_days": 7, "percent": 100, **configured}
        registered = self.types.get(product_type)
        refundable = registered.refundable_by_default if registered else False
        return {
            "refundable": refundable,
            "window_days": 7 if refundable else 0,
            "percent": 100 if refundable else 0,
        }

    def _validate(self, product_type: str, version: ProductVersionIn) -> None:
        registered = self.types.get(product_type)
        if registered is None:
            raise ValidationFailed("Unknown product type.", code="marketplace.invalid_product")
        check_payload(version.payload, registered.payload_fields)

    def _version_row(
        self, product: Product, number: int, version: ProductVersionIn, actor: Principal
    ) -> ProductVersion:
        payload = dict(version.payload)
        if product.type in ("feature", "plugin"):
            payload["config_required"] = version.config_required
        return ProductVersion(
            product_id=product.id,
            version=number,
            price_coins=version.price_coins,
            conditions=[c.model_dump() for c in version.conditions],
            refund_policy=self._policy(product.type, version),
            names=dict(version.names),
            descriptions=dict(version.descriptions),
            payload=payload,
            config_required=version.config_required,
            effective_from=utc_now(self.clock),
            changed_by=actor_id(actor),
        )

    # --- categories ----------------------------------------------------------------------------------
    async def categories(self) -> list[Category]:
        async with self.database.session() as session:
            return list(
                (await session.execute(select(Category).order_by(Category.position, Category.key))).scalars()
            )

    async def add_category(
        self, key: str, label_key: str, position: int = 0, icon: str | None = None
    ) -> Category:
        async with self.database.unit_of_work() as uow:
            existing = await uow.session.scalar(select(Category).where(Category.key == key))
            if existing is not None:
                if icon and existing.icon != icon:
                    existing.icon = icon
                return existing
            category = Category(key=key, label_key=label_key, position=position, icon=icon)
            uow.session.add(category)
        return category

    # --- products ------------------------------------------------------------------------------------
    async def create(self, actor: Principal, raw: dict[str, Any]) -> Product:
        data = parse_product(raw)
        self._validate(data.type, data.version)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            if await session.scalar(select(Product.id).where(Product.key == data.key)) is not None:
                raise Conflict("A product with this key exists.", code="marketplace.product_exists")
            category = None
            if data.category:
                category = await session.scalar(select(Category.id).where(Category.key == data.category))
                if category is None:
                    raise ValidationFailed("Unknown category.", code="marketplace.invalid_product")
            product = Product(
                key=data.key,
                type=data.type,
                category_id=category,
                state="draft",
                current_version=1,
                repeatable=data.repeatable,
                rarity=data.presentation.rarity,
                featured=data.presentation.featured,
                poster_effect=data.presentation.poster_effect,
                icon=data.presentation.icon,
                season=data.presentation.season,
                supply=data.availability.supply,
                limit_count=data.availability.limit_count,
                limit_days=data.availability.limit_days,
                created_by=actor_id(actor),
                created_at=now,
                updated_at=now,
            )
            session.add(product)
            await session.flush()
            session.add(self._version_row(product, 1, data.version, actor))
            await self._audit(session, actor, "product_created", product, type=data.type)
        return product

    async def revise(self, actor: Principal, key: str, raw: dict[str, Any]) -> Product:
        """Price, conditions, refund policy, texts or payload change ⇒ a new version (history kept)."""
        version = parse_version(raw)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            product = await session.scalar(select(Product).where(Product.key == key).with_for_update())
            if product is None:
                raise ProductNotFound("This product does not exist.")
            self._validate(product.type, version)
            number = (
                int(
                    await session.scalar(
                        select(func.max(ProductVersion.version)).where(
                            ProductVersion.product_id == product.id
                        )
                    )
                    or 0
                )
                + 1
            )
            session.add(self._version_row(product, number, version, actor))
            product.current_version, product.updated_at = number, utc_now(self.clock)
            await self._audit(session, actor, "product_revised", product, price=version.price_coins)
        return product

    async def present(
        self, actor: Principal, key: str, presentation: PresentationIn, category: str | None
    ) -> Product:
        """Shop presentation and collection (027 US8): merchandising only — no new version, audited."""
        async with self.database.unit_of_work() as uow:
            session = uow.session
            product = await session.scalar(select(Product).where(Product.key == key).with_for_update())
            if product is None:
                raise ProductNotFound("This product does not exist.")
            category_id = None
            if category:
                category_id = await session.scalar(select(Category.id).where(Category.key == category))
                if category_id is None:
                    raise ValidationFailed("Unknown collection.", code="marketplace.invalid_product")
            product.rarity, product.featured = presentation.rarity, presentation.featured
            product.poster_effect, product.icon = presentation.poster_effect, presentation.icon
            product.season = presentation.season
            product.category_id, product.updated_at = category_id, utc_now(self.clock)
            await self._audit(session, actor, "product_presented", product, rarity=presentation.rarity)
        return product

    async def set_availability(
        self,
        actor: Principal,
        key: str,
        availability: AvailabilityIn,
        min_level: int | None,
        min_contribution: int | None = None,
    ) -> Product:
        """027: copies, purchase limit, minimum level and minimum contribution. Those two are conditions, so
        changing one makes a new version (the current one copied with the new conditions) — purchases keep
        their snapshot."""
        async with self.database.unit_of_work() as uow:
            session = uow.session
            product = await session.scalar(select(Product).where(Product.key == key).with_for_update())
            if product is None:
                raise ProductNotFound("This product does not exist.")
            product.supply = availability.supply
            product.limit_count, product.limit_days = availability.limit_count, availability.limit_days
            product.updated_at = utc_now(self.clock)
            current = await session.get(ProductVersion, (product.id, product.current_version))
            assert current is not None
            if min_level != self.min_level_of(current) or min_contribution != self.min_contribution_of(
                current
            ):
                others = [
                    c for c in current.conditions if c.get("kind") not in ("min_level", "min_contribution")
                ]
                conditions = (
                    others
                    + ([{"kind": "min_level", "level": min_level}] if min_level else [])
                    + (
                        [{"kind": "min_contribution", "contribution": min_contribution}]
                        if min_contribution
                        else []
                    )
                )
                number = (
                    int(
                        await session.scalar(
                            select(func.max(ProductVersion.version)).where(
                                ProductVersion.product_id == product.id
                            )
                        )
                        or 0
                    )
                    + 1
                )
                session.add(
                    ProductVersion(
                        product_id=product.id,
                        version=number,
                        price_coins=current.price_coins,
                        conditions=conditions,
                        refund_policy=dict(current.refund_policy),
                        names=dict(current.names),
                        descriptions=dict(current.descriptions),
                        payload=dict(current.payload),
                        config_required=current.config_required,
                        effective_from=utc_now(self.clock),
                        changed_by=actor_id(actor),
                    )
                )
                product.current_version = number
            await self._audit(
                session,
                actor,
                "product_availability",
                product,
                **availability.model_dump(),
                min_level=min_level,
                min_contribution=min_contribution,
            )
        return product

    @staticmethod
    def min_level_of(version: ProductVersion) -> int | None:
        levels = [int(c["level"]) for c in version.conditions if c.get("kind") == "min_level"]
        return max(levels) if levels else None

    @staticmethod
    def min_contribution_of(version: ProductVersion) -> int | None:
        points = [int(c["contribution"]) for c in version.conditions if c.get("kind") == "min_contribution"]
        return max(points) if points else None

    async def move(self, actor: Principal, key: str, target: State) -> Product:
        async with self.database.unit_of_work() as uow:
            session = uow.session
            product = await session.scalar(select(Product).where(Product.key == key).with_for_update())
            if product is None:
                raise ProductNotFound("This product does not exist.")
            if target not in MOVES[product.state]:
                raise Conflict(
                    f"A product cannot go from {product.state} to {target}.", code="marketplace.invalid_state"
                )
            source, product.state, product.updated_at = product.state, target, utc_now(self.clock)
            action = {"available": "product_published", "archived": "product_archived"}.get(
                target, "product_unavailable"
            )
            await self._audit(session, actor, action, product, **{"from": source})
            if target in ("available", "archived"):
                await self.events.publish(
                    session,
                    f"marketplace.{action}",
                    {"product": product.key, "version": product.current_version},
                    occurred_at=utc_now(self.clock),
                    actor=actor,
                    subject=SubjectRef("product", product.key),
                    dedup_key=f"marketplace.{action}:{product.key}:{product.current_version}:{product.updated_at.isoformat()}",
                )
        return product

    # --- reads ---------------------------------------------------------------------------------------
    async def get(self, key: str) -> tuple[Product, ProductVersion]:
        async with self.database.session() as session:
            product = await session.scalar(select(Product).where(Product.key == key))
            if product is None:
                raise ProductNotFound("This product does not exist.")
            version = await session.get(ProductVersion, (product.id, product.current_version))
        assert version is not None
        return product, version

    async def version(self, product_id: UUID, number: int) -> ProductVersion | None:
        async with self.database.session() as session:
            return await session.get(ProductVersion, (product_id, number))

    async def listing(
        self,
        *,
        category: str | None = None,
        product_type: str | None = None,
        q: str | None = None,
        states: tuple[str, ...] = ("available",),
        owned_ids: set[UUID] | None = None,
        # the shop's whole catalogue in one answer, never cut: a cap in the query silently dropped the last
        # products by key — the themes past 500 (#80), then the theme packs and widgets past 1000 (#91); a
        # ``limit`` applies after the text filter, so a search looks through every product
        limit: int | None = None,
    ) -> list[tuple[Product, ProductVersion]]:
        statement = (
            select(Product, ProductVersion)
            .join(
                ProductVersion,
                (ProductVersion.product_id == Product.id)
                & (ProductVersion.version == Product.current_version),
            )
            .order_by(Product.key)
        )
        if owned_ids is not None:
            statement = statement.where((Product.state.in_(states)) | (Product.id.in_(owned_ids)))
        else:
            statement = statement.where(Product.state.in_(states))
        if category:
            statement = statement.join(Category, Category.id == Product.category_id).where(
                Category.key == category
            )
        if product_type:
            statement = statement.where(Product.type == product_type)
        async with self.database.session() as session:
            rows = [(p, v) for p, v in (await session.execute(statement)).all()]
        if q:
            needle = q.strip().casefold()
            rows = [
                (p, v)
                for p, v in rows
                if needle in p.key.casefold() or any(needle in n.casefold() for n in v.names.values())
            ]
        return rows if limit is None else rows[: max(1, limit)]
