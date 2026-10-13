"""The shop's console for administrators (#98): what is going on (purchases and Coins spent day by day, the
best sellers, boosters opened, requests waiting, refunds, the latest activity), the catalogue a page at a
time (searchable — the whole shop is over a thousand products), a member's inventory, a purchase taken out
of the history, and the seasons' weeks (a season's booster is on sale in them only)."""

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, or_, select

from portalab.core.audit_port import AuditRecord
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, NotFound
from portalab.core.time import utc_now
from portalab.modules.marketplace.activation.service import LIVE
from portalab.modules.marketplace.api.catalog import MarketplaceProductOut, category_keys, product_out
from portalab.modules.marketplace.api.projects import Module
from portalab.modules.marketplace.boosters import SEASONS, in_window
from portalab.modules.marketplace.models import (
    BoosterOpening,
    MarketRequest,
    Ownership,
    Product,
    ProductVersion,
    Refund,
)
from portalab.modules.marketplace.permissions import MANAGE, REVOKE

router = APIRouter(prefix="/api/v1", tags=["marketplace-admin"])
Manager = Annotated[Principal, require(MANAGE)]
Revoker = Annotated[Principal, require(REVOKE)]
STATES = ("draft", "available", "unavailable", "archived")


class DayOut(BaseModel):
    day: date
    purchases: int
    coins: int
    grants: int
    boosters: int


class TopProductOut(BaseModel):
    key: str
    type: str
    names: dict[str, str]
    count: int
    coins: int


class ActivityOut(BaseModel):
    kind: Literal["purchase", "grant", "booster_item", "booster", "revoked", "refunded", "request"]
    at: datetime
    user_id: UUID
    product: str | None = None
    names: dict[str, str] = {}
    coins: int = 0
    ownership_id: UUID | None = None
    state: str | None = None


class OverviewOut(BaseModel):
    days: int
    purchases: int
    coins_spent: int
    buyers: int
    grants: int
    boosters_opened: int
    booster_coins: int
    refunds: int
    requests_pending: int
    products_on_sale: int
    items_owned: int
    series: list[DayOut]
    top: list[TopProductOut]
    activity: list[ActivityOut]


class CatalogPageOut(BaseModel):
    items: list[MarketplaceProductOut]
    total: int
    types: dict[str, int]


class InventoryItemOut(BaseModel):
    ownership_id: UUID
    product: str
    type: str
    rarity: str
    names: dict[str, str]
    origin: str
    price_paid: int
    state: str
    acquired_at: datetime
    revoked_at: datetime | None
    revoke_ground: str | None
    refunded: bool


class SeasonOut(BaseModel):
    key: str
    start: tuple[int, int]  # (month, day)
    end: tuple[int, int]
    now: bool


class RemoveIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.get("/admin/marketplace/overview", response_model=OverviewOut)
async def overview(_: Manager, module: Module, days: Annotated[int, Query(ge=1, le=365)] = 30) -> OverviewOut:
    now = utc_now(module.clock)
    since = now - timedelta(days=days)
    async with module.database.session() as session:
        owned = (
            await session.execute(
                select(Ownership, Product, ProductVersion)
                .join(Product, Product.id == Ownership.product_id)
                .join(
                    ProductVersion,
                    and_(
                        ProductVersion.product_id == Ownership.product_id,
                        ProductVersion.version == Ownership.product_version,
                    ),
                )
                .where(or_(Ownership.acquired_at >= since, Ownership.revoked_at >= since))
            )
        ).all()
        openings = list(
            (await session.execute(select(BoosterOpening).where(BoosterOpening.opened_at >= since))).scalars()
        )
        refunds = list((await session.execute(select(Refund).where(Refund.created_at >= since))).scalars())
        requests = list(
            (
                await session.execute(
                    select(MarketRequest, Product, ProductVersion)
                    .join(Product, Product.id == MarketRequest.product_id)
                    .join(
                        ProductVersion,
                        and_(
                            ProductVersion.product_id == Product.id,
                            ProductVersion.version == Product.current_version,
                        ),
                    )
                    .where(MarketRequest.created_at >= since)
                )
            ).all()
        )
        pending = int(await session.scalar(select(func.count()).where(MarketRequest.state == "pending")) or 0)
        on_sale = int(await session.scalar(select(func.count()).where(Product.state == "available")) or 0)
        live = int(await session.scalar(select(func.count()).where(Ownership.state.in_(LIVE))) or 0)
        booster_names = {
            key: names
            for key, names in (
                await session.execute(
                    select(Product.key, ProductVersion.names)
                    .join(
                        ProductVersion,
                        and_(
                            ProductVersion.product_id == Product.id,
                            ProductVersion.version == Product.current_version,
                        ),
                    )
                    .where(Product.key.in_({o.booster_key for o in openings}))
                )
            ).all()
        }
    series = {
        (since + timedelta(days=i + 1)).date(): {"purchases": 0, "coins": 0, "grants": 0, "boosters": 0}
        for i in range(days)
    }
    top: dict[str, dict[str, Any]] = {}
    activity: list[ActivityOut] = []
    buyers: set[UUID] = set()
    purchases = coins = grants = 0
    for ownership, product, version in owned:
        names = dict(version.names or {})
        if ownership.acquired_at >= since:
            day = series.get(ownership.acquired_at.date())
            if ownership.origin == "purchase":
                purchases += 1
                coins += ownership.price_paid
                buyers.add(ownership.user_id)
                if day:
                    day["purchases"] += 1
                    day["coins"] += ownership.price_paid
                entry = top.setdefault(
                    product.key,
                    {"key": product.key, "type": product.type, "names": names, "count": 0, "coins": 0},
                )
                entry["count"] += 1
                entry["coins"] += ownership.price_paid
            elif ownership.origin == "grant":
                grants += 1
                if day:
                    day["grants"] += 1
            activity.append(
                ActivityOut(
                    kind="purchase"
                    if ownership.origin == "purchase"
                    else "grant"
                    if ownership.origin == "grant"
                    else "booster_item",
                    at=ownership.acquired_at,
                    user_id=ownership.user_id,
                    product=product.key,
                    names=names,
                    coins=ownership.price_paid,
                    ownership_id=ownership.id,
                    state=ownership.state,
                )
            )
        if ownership.revoked_at is not None and ownership.revoked_at >= since:
            activity.append(
                ActivityOut(
                    kind="refunded" if ownership.state == "refunded" else "revoked",
                    at=ownership.revoked_at,
                    user_id=ownership.user_id,
                    product=product.key,
                    names=names,
                    ownership_id=ownership.id,
                    state=ownership.state,
                )
            )
    booster_coins = 0
    for opening in openings:
        booster_coins += opening.price - opening.refund
        day = series.get(opening.opened_at.date())
        if day:
            day["boosters"] += 1
            day["coins"] += opening.price - opening.refund
        activity.append(
            ActivityOut(
                kind="booster",
                at=opening.opened_at,
                user_id=opening.user_id,
                product=opening.booster_key,
                names=dict(booster_names.get(opening.booster_key) or {}),
                coins=opening.price - opening.refund,
            )
        )
    for request, product, version in requests:
        activity.append(
            ActivityOut(
                kind="request",
                at=request.created_at,
                user_id=request.user_id,
                product=product.key,
                names=dict(version.names or {}),
                ownership_id=request.ownership_id,
                state=request.state,
            )
        )
    activity.sort(key=lambda a: a.at, reverse=True)
    return OverviewOut(
        days=days,
        purchases=purchases,
        coins_spent=coins + booster_coins,
        buyers=len(buyers | {o.user_id for o in openings}),
        grants=grants,
        boosters_opened=len(openings),
        booster_coins=booster_coins,
        refunds=len(refunds),
        requests_pending=pending,
        products_on_sale=on_sale,
        items_owned=live,
        series=[DayOut(day=day, **values) for day, values in sorted(series.items())],
        top=[
            TopProductOut(**entry)
            for entry in sorted(top.values(), key=lambda e: (-e["count"], -e["coins"]))[:10]
        ],
        activity=activity[:60],
    )


@router.get("/admin/marketplace/catalog", response_model=CatalogPageOut)
async def catalog(
    _: Manager,
    module: Module,
    q: Annotated[str | None, Query(max_length=100)] = None,
    type: Annotated[str | None, Query(max_length=96, pattern=r"^[a-z][a-z0-9_.]*$")] = None,
    state: Annotated[str | None, Query(pattern=r"^(draft|available|unavailable|archived)$")] = None,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=2000)] = 40,
) -> CatalogPageOut:
    """A page of the catalogue (the whole shop is too big for one page), searched by key or name, with how
    many products of each type the search finds."""
    rows = await module.catalog.listing(states=(state,) if state else STATES, q=q or None)
    types = Counter(product.type for product, _ in rows)
    if type:
        rows = [(p, v) for p, v in rows if p.type == type]
    keys = await category_keys(module)
    page = rows[offset : offset + limit]
    stock = await module.availability.stock(p for p, _ in page)
    return CatalogPageOut(
        items=[product_out(p, v, False, categories=keys, stock=stock) for p, v in page],
        total=len(rows),
        types=dict(types),
    )


@router.get("/admin/marketplace/members/{user_id}/inventory", response_model=list[InventoryItemOut])
async def inventory(_: Manager, module: Module, user_id: UUID) -> list[InventoryItemOut]:
    """Every item a member holds or held — live ones first, then the history."""
    async with module.database.session() as session:
        rows = (
            await session.execute(
                select(Ownership, Product, ProductVersion)
                .join(Product, Product.id == Ownership.product_id)
                .join(
                    ProductVersion,
                    and_(
                        ProductVersion.product_id == Ownership.product_id,
                        ProductVersion.version == Ownership.product_version,
                    ),
                )
                .where(Ownership.user_id == user_id)
            )
        ).all()
        refunded = set(
            (
                await session.execute(
                    select(Refund.ownership_id).where(Refund.ownership_id.in_([o.id for o, _, _ in rows]))
                )
            ).scalars()
        )
    items = [
        InventoryItemOut(
            ownership_id=ownership.id,
            product=product.key,
            type=product.type,
            rarity=product.rarity,
            names=dict(version.names or {}),
            origin=ownership.origin,
            price_paid=ownership.price_paid,
            state=ownership.state,
            acquired_at=ownership.acquired_at,
            revoked_at=ownership.revoked_at,
            revoke_ground=ownership.revoke_ground,
            refunded=ownership.id in refunded,
        )
        for ownership, product, version in rows
    ]
    items.sort(key=lambda i: (i.state not in LIVE, -i.acquired_at.timestamp()))
    return items


@router.delete("/admin/marketplace/ownerships/{ownership_id}", status_code=204)
async def remove_from_history(
    principal: Revoker, module: Module, ownership_id: UUID, body: RemoveIn
) -> Response:
    """Take an item out of the member's history altogether — its effect off when it is still live (no
    Coins move: to give them back, refund it instead). One already refunded keeps its record (the refund is
    part of the ledger)."""
    async with module.database.session() as session:
        row = await session.get(Ownership, ownership_id)
        if row is None:
            raise NotFound("This ownership does not exist.", code="marketplace.not_owned")
        refunded = await session.scalar(select(func.count()).where(Refund.ownership_id == ownership_id))
    if refunded:
        raise Conflict("A refunded purchase stays in the history.", code="marketplace.refunded_kept")
    if row.state in LIVE:
        await module.activation.deactivate(row)
    async with module.database.unit_of_work() as uow:
        session = uow.session
        await session.execute(delete(MarketRequest).where(MarketRequest.ownership_id == ownership_id))
        await session.execute(delete(Ownership).where(Ownership.id == ownership_id))
        await module.audit.record(
            session,
            AuditRecord(
                action="marketplace.removed_from_history",
                actor=principal,
                resource=ResourceRef("ownership", str(ownership_id), owner_id=row.user_id),
                decision="allow",
                context={"reason": body.reason[:200]},
                sensitive=True,
            ),
        )
    return Response(status_code=204)


@router.get("/admin/marketplace/seasons", response_model=list[SeasonOut])
async def seasons(_: Manager, module: Module) -> list[SeasonOut]:
    """The seasons' weeks: a season's booster is on sale in them only."""
    today = utc_now(module.clock).date()
    return [
        SeasonOut(key=key, start=season.window[0], end=season.window[1], now=in_window(season.window, today))
        for key, season in SEASONS.items()
    ]
