"""Marketplace administration (T021, T028, T030): ``marketplace.manage`` for products (publishing and every
new version are sensitive and need a confirmation), ``marketplace.grant``, ``marketplace.revoke``,
``marketplace.refund`` (confirmed) and ``marketplace.audit`` (the marketplace audit trail)."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from portalab.capabilities.administration import AUDIT_QUERY_CAPABILITY
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.marketplace.api.admin import _confirm_generic
from portalab.modules.marketplace.api.catalog import (
    MarketplaceOwnershipOut,
    MarketplaceProductOut,
    category_keys,
    ownership_out,
    product_out,
)
from portalab.modules.marketplace.api.projects import Module
from portalab.modules.marketplace.permissions import AUDIT, GRANT, MANAGE, REFUND, REVOKE
from portalab.modules.marketplace.products.definition import AvailabilityIn, PresentationIn

router = APIRouter(prefix="/api/v1", tags=["marketplace-admin"])
Manager = Annotated[Principal, require(MANAGE)]
Granter = Annotated[Principal, require(GRANT)]
Revoker = Annotated[Principal, require(REVOKE)]
Refunder = Annotated[Principal, require(REFUND)]
Auditor = Annotated[Principal, require(AUDIT)]


class MarketplaceProductIn(BaseModel):
    definition: dict[str, Any]
    confirmation: str | None = None


class MarketplaceCategoryIn(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)
    label_key: str = Field(min_length=1, max_length=160)
    position: int = 0
    icon: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{0,63}$")


class MarketplacePresentationIn(BaseModel):
    """027 US8: shop presentation and collection — merchandising, no new price version."""

    presentation: PresentationIn
    category: str | None = Field(default=None, max_length=64)


class MarketplaceAvailabilityIn(BaseModel):
    """027: copies, purchase limit per period, minimum level and minimum contribution (conditions: a new
    version)."""

    availability: AvailabilityIn
    min_level: int | None = Field(default=None, ge=1, le=1000)
    min_contribution: int | None = Field(default=None, ge=1, le=1_000_000)
    confirmation: str | None = None


class MarketplaceRaritiesIn(BaseModel):
    supply: dict[str, int | None]


class MarketplaceConfirmIn(BaseModel):
    confirmation: str | None = None


class MarketplaceGrantIn(BaseModel):
    user_id: UUID
    product: str = Field(max_length=96)
    reason: str = Field(min_length=1, max_length=500)
    expires_at: datetime | None = None
    confirmation: str | None = None


class MarketplaceRevokeIn(BaseModel):
    ground: Literal["abuse", "grant_expired", "refund", "withdrawn_for_cause"]
    reason: str = Field(min_length=1, max_length=500)
    confirmation: str | None = None


class MarketplaceAdminRefundIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    percent: int | None = Field(default=None, ge=0, le=100)
    confirmation: str | None = None


class MarketplaceAuditPage(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: str | None


@router.get("/admin/marketplace/products", response_model=list[MarketplaceProductOut])
async def admin_products(_: Manager, module: Module) -> list[MarketplaceProductOut]:
    rows = await module.catalog.listing(states=("draft", "available", "unavailable", "archived"))
    keys = await category_keys(module)
    stock = await module.availability.stock(p for p, _ in rows)
    return [product_out(p, v, False, categories=keys, stock=stock) for p, v in rows]


@router.get("/admin/marketplace/rarities")
async def rarities(_: Manager, module: Module) -> dict[str, int | None]:
    """027: how many copies a product of each rarity may have (``null``: unlimited)."""
    return await module.availability.rarities()


@router.put("/admin/marketplace/rarities")
async def set_rarities(
    principal: Manager, body: MarketplaceRaritiesIn, module: Module
) -> dict[str, int | None]:
    return await module.availability.set_rarities(principal, body.supply)


@router.put("/admin/marketplace/products/{key}/availability", response_model=MarketplaceProductOut)
async def product_availability(
    principal: Manager, key: str, body: MarketplaceAvailabilityIn, module: Module
) -> MarketplaceProductOut:
    product, version = await module.catalog.get(key)
    if product.state != "draft" and (
        body.min_level != module.catalog.min_level_of(version)
        or body.min_contribution != module.catalog.min_contribution_of(version)
    ):
        await _confirm_generic(  # a published product's conditions change is sensitive
            module, principal, MANAGE, f"product:{key}", {"revise": key}, body.confirmation
        )
    await module.catalog.set_availability(
        principal, key, body.availability, body.min_level, body.min_contribution
    )
    product, version = await module.catalog.get(key)
    stock = await module.availability.stock([product])
    return product_out(product, version, False, categories=await category_keys(module), stock=stock)


@router.post("/admin/marketplace/categories", status_code=201)
async def add_category(_: Manager, body: MarketplaceCategoryIn, module: Module) -> dict[str, str]:
    category = await module.catalog.add_category(body.key, body.label_key, body.position, body.icon)
    return {"key": category.key}


@router.get("/admin/marketplace/types")
async def product_types(_: Manager, module: Module) -> list[dict[str, Any]]:
    """The kinds of products the shop can sell now — Portalab's and those enabled plugins add (spec 030)."""
    return [
        {
            "key": t.key,
            "owner": t.owner,
            "label_key": t.label_key,
            "payload_fields": list(t.payload_fields),
            "refundable_by_default": t.refundable_by_default,
        }
        for t in sorted(module.catalog.types.all(), key=lambda t: t.key)
    ]


@router.post("/admin/marketplace/products", response_model=MarketplaceProductOut, status_code=201)
async def create_product(
    principal: Manager, body: MarketplaceProductIn, module: Module
) -> MarketplaceProductOut:
    product = await module.catalog.create(principal, body.definition)
    _, version = await module.catalog.get(product.key)
    return product_out(product, version, False, categories=await category_keys(module))


@router.put("/admin/marketplace/products/{key}", response_model=MarketplaceProductOut)
async def revise_product(
    principal: Manager, key: str, body: MarketplaceProductIn, module: Module
) -> MarketplaceProductOut:
    product, _ = await module.catalog.get(key)
    if product.state != "draft":  # a published product's price/conditions change is sensitive
        await _confirm_generic(
            module, principal, MANAGE, f"product:{key}", {"revise": key}, body.confirmation
        )
    product = await module.catalog.revise(principal, key, body.definition)
    _, version = await module.catalog.get(key)
    return product_out(product, version, False)


@router.put("/admin/marketplace/products/{key}/presentation", response_model=MarketplaceProductOut)
async def present_product(
    principal: Manager, key: str, body: MarketplacePresentationIn, module: Module
) -> MarketplaceProductOut:
    await module.catalog.present(principal, key, body.presentation, body.category)
    product, version = await module.catalog.get(key)
    return product_out(product, version, False, categories=await category_keys(module))


@router.post("/admin/marketplace/grants", response_model=MarketplaceOwnershipOut, status_code=201)
async def grant(principal: Granter, body: MarketplaceGrantIn, module: Module) -> MarketplaceOwnershipOut:
    await _confirm_generic(
        module, principal, GRANT, f"user:{body.user_id}", {"product": body.product}, body.confirmation
    )
    row = await module.grants.grant(principal, body.user_id, body.product, body.reason, body.expires_at)
    return await ownership_out(module, row)


@router.post("/admin/marketplace/ownerships/{ownership_id}/revoke", response_model=MarketplaceOwnershipOut)
async def revoke(
    principal: Revoker, ownership_id: UUID, body: MarketplaceRevokeIn, module: Module
) -> MarketplaceOwnershipOut:
    await _confirm_generic(
        module, principal, REVOKE, f"ownership:{ownership_id}", {"ground": body.ground}, body.confirmation
    )
    return await ownership_out(
        module, await module.revocations.revoke(principal, ownership_id, body.ground, body.reason)
    )


@router.post("/admin/marketplace/ownerships/{ownership_id}/refund", response_model=MarketplaceOwnershipOut)
async def admin_refund(
    principal: Refunder, ownership_id: UUID, body: MarketplaceAdminRefundIn, module: Module
) -> MarketplaceOwnershipOut:
    await _confirm_generic(
        module, principal, REFUND, f"ownership:{ownership_id}", {"percent": body.percent}, body.confirmation
    )
    row = await module.refunds.refund(
        principal, ownership_id, body.reason, by_admin=True, percent=body.percent
    )
    return await ownership_out(module, row)


@router.get("/admin/marketplace/audit", response_model=MarketplaceAuditPage)
async def audit(
    principal: Auditor,
    module: Module,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> MarketplaceAuditPage:
    providers = module.capabilities.system_providers(AUDIT_QUERY_CAPABILITY)
    if not providers:
        raise Unavailable("The audit is not available.", code="audit.unavailable")
    items, next_cursor = await providers[0].provider.search_actions(
        principal, "marketplace.", limit=limit, cursor=cursor
    )
    return MarketplaceAuditPage(items=items, next_cursor=next_cursor)


@router.post("/admin/marketplace/products/{key}/{transition}", response_model=MarketplaceProductOut)
async def move_product(
    principal: Manager,
    key: str,
    transition: Literal["publish", "unavailable", "archive"],
    body: MarketplaceConfirmIn,
    module: Module,
) -> MarketplaceProductOut:
    target = {"publish": "available", "unavailable": "unavailable", "archive": "archived"}[transition]
    if transition == "publish":
        await _confirm_generic(
            module, principal, MANAGE, f"product:{key}", {"publish": key}, body.confirmation
        )
    product = await module.catalog.move(principal, key, target)  # type: ignore[arg-type]
    _, version = await module.catalog.get(key)
    return product_out(product, version, False)
