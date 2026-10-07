"""Marketplace catalog API (T020, T024, T026, T028): ``marketplace.read`` to browse (product detail shows
type, price, conditions **with the viewer's eligibility by name**, refund policy and the viewer's
ownership), ``marketplace.purchase`` to acquire (``Idempotency-Key``), and the member's own purchases,
owned products, configuration and refunds."""

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from portalab.capabilities.campaigns import ShopDiscount
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.time import utc_now
from portalab.modules.marketplace.activation.service import LIVE
from portalab.modules.marketplace.api.projects import Module
from portalab.modules.marketplace.integrations import name_of
from portalab.modules.marketplace.models import Ownership, Product, ProductVersion
from portalab.modules.marketplace.module import MarketplaceModule
from portalab.modules.marketplace.permissions import PURCHASE, READ
from portalab.modules.marketplace.pricing import active_discounts, price_now
from portalab.modules.marketplace.products.service import ProductNotFound

router = APIRouter(prefix="/api/v1", tags=["marketplace"])
Reader = Annotated[Principal, require(READ)]
Buyer = Annotated[Principal, require(PURCHASE)]
Me = Annotated[Principal, require("users.self.manage")]


class MarketplaceCategoryOut(BaseModel):
    key: str
    label_key: str
    icon: str | None = None


class MarketplaceCheckOut(BaseModel):
    name: str
    value: Any
    met: bool
    reason: str


class MarketplaceDiscountOut(BaseModel):
    percent: int
    campaign: str
    name: str
    names: dict[str, str] = Field(default_factory=dict)
    ends_at: datetime | None = None


class MarketplaceProductOut(BaseModel):
    key: str
    type: str
    state: str
    version: int
    name: str
    names: dict[str, str]
    descriptions: dict[str, str]
    price_coins: int | None
    conditions: list[dict[str, Any]]
    refund_policy: dict[str, Any]
    config_required: bool
    repeatable: bool
    owned: bool
    rarity: str = "common"
    featured: bool = False
    poster_effect: str = "auto"
    icon: str | None = None
    category: str | None = None
    theme: str | None = None  # 027 US11: the theme a ``theme`` product unlocks (shown before buying)
    eligibility: list[MarketplaceCheckOut] = []
    preview: dict[str, Any] = Field(default_factory=dict)  # 027: what the shop previews before buying
    # 027 scarcity: copies in all (None: unlimited) and left, purchase limit per period, minimum level
    supply: int | None = None
    remaining: int | None = None
    limit_count: int | None = None
    limit_days: int | None = None
    min_level: int | None = None
    # 027: the price now and the campaign reduction behind it (None: the catalog price applies)
    price_now: int | None = None
    discount: MarketplaceDiscountOut | None = None


# 027: the payload fields a product's preview may show (never configuration or extension details)
PREVIEW_FIELDS: dict[str, tuple[str, ...]] = {
    "theme": ("theme",),
    "widget": ("widget",),
    "badge": ("label", "icon", "style"),
    "title": ("label", "style"),
    "effect": ("effect",),
    "quota": ("kind", "units"),
    "notification_style": ("style",),
    "notification_animation": ("animation",),
    "bundle": ("products",),
    "profile_banner": ("banner",),
    "avatar_frame": ("frame",),
    "profile_backdrop": ("feature",),
    "palette": ("palette",),
    "ambient": ("ambient",),
    "profile_background": ("background",),
    "name_style": ("style",),
    "level_badge": ("style",),
    "widget_option": ("option",),
    "project_launch": ("kind",),
    "statistic": ("statistic",),
}


class MarketplaceOwnershipOut(BaseModel):
    id: UUID
    product_key: str
    product_type: str
    product_name: str
    origin: str
    state: str
    price_paid: int
    product_version: int
    conditions_snapshot: list[dict[str, Any]]
    refundable_until: datetime | None
    acquired_at: datetime
    expires_at: datetime | None
    revoke_ground: str | None


class MarketplaceConfigureIn(BaseModel):
    configuration: dict[str, Any] = Field(default_factory=dict)


class MarketplaceRefundIn(BaseModel):
    reason: str = Field(default="Changed my mind", min_length=1, max_length=500)


def _me(principal: Principal) -> UUID:
    user = principal.acting_for or principal.user_id
    assert user is not None
    return user


def product_out(
    product: Product,
    version: ProductVersion,
    owned: bool,
    language: str = "en",
    categories: Mapping[UUID, str] | None = None,
    stock: Mapping[UUID, tuple[int | None, int | None]] | None = None,
    discounts: Sequence[ShopDiscount] = (),
) -> MarketplaceProductOut:
    supply, remaining = (stock or {}).get(product.id, (None, None))
    category = (categories or {}).get(product.category_id) if product.category_id else None
    now, discount = price_now(discounts, product.key, category, version.price_coins)
    levels = [int(c["level"]) for c in version.conditions if c.get("kind") == "min_level"]
    return MarketplaceProductOut(
        key=product.key,
        type=product.type,
        state=product.state,
        version=version.version,
        name=name_of(version, language),
        names=dict(version.names),
        descriptions=dict(version.descriptions),
        price_coins=version.price_coins,
        conditions=list(version.conditions),
        refund_policy=dict(version.refund_policy),
        config_required=version.config_required,
        repeatable=product.repeatable,
        owned=owned,
        rarity=product.rarity,
        featured=product.featured,
        poster_effect=product.poster_effect,
        icon=product.icon,
        category=category,
        theme=str(version.payload.get("theme")) if product.type == "theme" and version.payload else None,
        preview={
            field: (version.payload or {})[field]
            for field in PREVIEW_FIELDS.get(product.type, ())
            if field in (version.payload or {})
        },
        supply=supply,
        remaining=remaining,
        limit_count=product.limit_count,
        limit_days=product.limit_days,
        min_level=max(levels) if levels else None,
        price_now=now,
        discount=MarketplaceDiscountOut(
            percent=discount.percent,
            campaign=discount.campaign,
            name=discount.names.get(language) or discount.name,
            names=dict(discount.names),
            ends_at=discount.ends_at,
        )
        if discount
        else None,
    )


async def category_keys(module: MarketplaceModule) -> dict[UUID, str]:
    return {c.id: c.key for c in await module.catalog.categories()}


async def ownership_out(module: MarketplaceModule, row: Ownership) -> MarketplaceOwnershipOut:
    async with module.database.session() as session:
        product = await session.get(Product, row.product_id)
        version = await session.get(ProductVersion, (row.product_id, row.product_version))
    assert product is not None and version is not None
    policy = dict(version.refund_policy)
    until = (
        row.acquired_at + timedelta(days=int(policy.get("window_days", 0)))
        if policy.get("refundable") and row.origin == "purchase" and row.price_paid > 0
        else None
    )
    return MarketplaceOwnershipOut(
        id=row.id,
        product_key=product.key,
        product_type=product.type,
        product_name=name_of(version),
        origin=row.origin,
        state=row.state,
        price_paid=row.price_paid,
        product_version=row.product_version,
        conditions_snapshot=list(row.conditions_snapshot),
        refundable_until=until,
        acquired_at=row.acquired_at,
        expires_at=row.expires_at,
        revoke_ground=row.revoke_ground,
    )


async def owned_ids(module: MarketplaceModule, user: UUID) -> set[UUID]:
    async with module.database.session() as session:
        rows = await session.execute(
            select(Ownership.product_id).where(Ownership.user_id == user, Ownership.state.in_(LIVE))
        )
        return set(rows.scalars())


@router.get("/marketplace/categories", response_model=list[MarketplaceCategoryOut])
async def categories(_: Reader, module: Module) -> list[MarketplaceCategoryOut]:
    return [
        MarketplaceCategoryOut(key=c.key, label_key=c.label_key, icon=c.icon)
        for c in await module.catalog.categories()
    ]


@router.get("/marketplace/products", response_model=list[MarketplaceProductOut])
async def products(
    principal: Reader,
    module: Module,
    category: Annotated[str | None, Query(max_length=64)] = None,
    type: Annotated[str | None, Query(max_length=96)] = None,
    q: Annotated[str | None, Query(max_length=64)] = None,
) -> list[MarketplaceProductOut]:
    mine = await owned_ids(module, _me(principal))
    rows = await module.catalog.listing(category=category, product_type=type, q=q, owned_ids=mine)
    keys = await category_keys(module)
    stock = await module.availability.stock(p for p, _ in rows)
    discounts = await active_discounts(module.capabilities, utc_now(module.clock))
    return [
        product_out(p, v, p.id in mine, categories=keys, stock=stock, discounts=discounts) for p, v in rows
    ]


@router.get("/marketplace/products/{key}", response_model=MarketplaceProductOut)
async def product_detail(principal: Reader, key: str, module: Module) -> MarketplaceProductOut:
    product, version = await module.catalog.get(key)
    user = _me(principal)
    mine = await owned_ids(module, user)
    if product.state in ("draft",) or (product.state == "archived" and product.id not in mine):
        raise ProductNotFound("This product does not exist.")
    stock = await module.availability.stock([product])
    discounts = await active_discounts(module.capabilities, utc_now(module.clock))
    out = product_out(
        product,
        version,
        product.id in mine,
        categories=await category_keys(module),
        stock=stock,
        discounts=discounts,
    )
    checks = await module.eligibility.checks(user, list(version.conditions), out.price_now)
    if product.id not in mine or product.repeatable:
        checks += await module.availability.checks(user, product)
    out.eligibility = [
        MarketplaceCheckOut(name=c.name, value=c.value, met=c.met, reason=c.reason) for c in checks
    ]
    return out


@router.post("/marketplace/products/{key}/acquire", response_model=MarketplaceOwnershipOut, status_code=201)
async def acquire(
    principal: Buyer,
    key: str,
    module: Module,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)] = None,
) -> MarketplaceOwnershipOut:
    row = await module.purchases.acquire(principal, key, idempotency_key or str(uuid4()))
    return await ownership_out(module, row)


@router.get("/me/marketplace/purchases", response_model=list[MarketplaceOwnershipOut])
async def purchases(principal: Me, module: Module) -> list[MarketplaceOwnershipOut]:
    async with module.database.session() as session:
        rows = list(
            (
                await session.execute(
                    select(Ownership)
                    .where(Ownership.user_id == _me(principal))
                    .order_by(Ownership.acquired_at.desc(), Ownership.id)
                )
            ).scalars()
        )
    return [await ownership_out(module, r) for r in rows]


@router.get("/me/marketplace/owned", response_model=list[MarketplaceOwnershipOut])
async def owned(principal: Me, module: Module) -> list[MarketplaceOwnershipOut]:
    return [o for o in await purchases(principal, module) if o.state in LIVE]


@router.post("/me/marketplace/owned/{ownership_id}/configure", response_model=MarketplaceOwnershipOut)
async def configure(
    principal: Me, ownership_id: UUID, body: MarketplaceConfigureIn, module: Module
) -> MarketplaceOwnershipOut:
    return await ownership_out(
        module, await module.activation.configure(principal, ownership_id, body.configuration)
    )


@router.post("/me/marketplace/owned/{ownership_id}/refund", response_model=MarketplaceOwnershipOut)
async def refund(
    principal: Me, ownership_id: UUID, body: MarketplaceRefundIn, module: Module
) -> MarketplaceOwnershipOut:
    return await ownership_out(module, await module.refunds.refund(principal, ownership_id, body.reason))


# --- 027: profile looks (banner, avatar frame, film backdrop) -------------------------------------------
class ProfileLookIn(BaseModel):
    slot: str = Field(pattern=r"^(banner|frame|backdrop|background|name|title|badges)$")
    value: Any = None


@router.get("/me/profile-looks")
async def my_profile_looks(principal: Me, module: Module) -> dict[str, Any]:
    """The designs a member may wear on their profile (those sold and not owned are locked)."""
    assert principal.user_id is not None
    return await module.looks.catalog(principal.user_id)


@router.put("/me/profile-looks")
async def equip_profile_look(principal: Me, body: ProfileLookIn, module: Module) -> dict[str, Any]:
    assert principal.user_id is not None
    return {"equipped": await module.looks.equip(principal.user_id, body.slot, body.value)}
