"""Marketplace catalog API (T020, T024, T026, T028): ``marketplace.read`` to browse (product detail shows
type, price, conditions **with the viewer's eligibility by name**, refund policy and the viewer's
ownership), ``marketplace.purchase`` to acquire (``Idempotency-Key``), and the member's own purchases,
owned products, configuration and refunds."""

from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.marketplace.activation.service import LIVE
from portalab.modules.marketplace.api.projects import Module
from portalab.modules.marketplace.integrations import name_of
from portalab.modules.marketplace.models import Ownership, Product, ProductVersion
from portalab.modules.marketplace.module import MarketplaceModule
from portalab.modules.marketplace.permissions import PURCHASE, READ
from portalab.modules.marketplace.products.service import ProductNotFound

router = APIRouter(prefix="/api/v1", tags=["marketplace"])
Reader = Annotated[Principal, require(READ)]
Buyer = Annotated[Principal, require(PURCHASE)]
Me = Annotated[Principal, require("users.self.manage")]


class MarketplaceCategoryOut(BaseModel):
    key: str
    label_key: str


class MarketplaceCheckOut(BaseModel):
    name: str
    value: Any
    met: bool
    reason: str


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
    eligibility: list[MarketplaceCheckOut] = []


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
    product: Product, version: ProductVersion, owned: bool, language: str = "en"
) -> MarketplaceProductOut:
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
    )


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
        MarketplaceCategoryOut(key=c.key, label_key=c.label_key) for c in await module.catalog.categories()
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
    return [product_out(p, v, p.id in mine) for p, v in rows]


@router.get("/marketplace/products/{key}", response_model=MarketplaceProductOut)
async def product_detail(principal: Reader, key: str, module: Module) -> MarketplaceProductOut:
    product, version = await module.catalog.get(key)
    user = _me(principal)
    mine = await owned_ids(module, user)
    if product.state in ("draft",) or (product.state == "archived" and product.id not in mine):
        raise ProductNotFound("This product does not exist.")
    out = product_out(product, version, product.id in mine)
    checks = await module.eligibility.checks(user, list(version.conditions), version.price_coins)
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
