"""Integrations (T020, T033): the ``product`` search provider (008, ``marketplace.read``), the dashboard
widgets ``marketplace.featured`` (009) and ``marketplace.reserve`` (#347), the read-only AI tool
``marketplace.catalog`` (018) and the ``cosmetics`` profile section (012: owned badges and titles, under the
owner's ``progression`` visibility)."""

import time
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.ai import AITool, SourceRef, ToolResult
from portalab.capabilities.community import ProfileSection, SectionResult
from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import snippet
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.entitlements.reader import Entitlements
from portalab.modules.marketplace.models import Ownership, Product, ProductVersion, ReserveItem, ReserveSeen
from portalab.modules.marketplace.permissions import READ
from portalab.modules.marketplace.products.service import Catalog

OWNER = "module:marketplace"


def name_of(version: ProductVersion, language: str = "en") -> str:
    names = dict(version.names)
    return (
        names.get(language)
        or names.get(language.split("-")[0])
        or names.get("en")
        or next(iter(names.values()), "")
    )


class ProductSearchProvider:
    kind = "product"
    label_key = "marketplace:search.product"
    required_permission = READ

    def __init__(self, catalog: Catalog, authorizer: Authorizer) -> None:
        self.catalog = catalog
        self.authorizer = authorizer

    def facets(self) -> Sequence[FacetDef]:
        return ()

    def _item(
        self, product: Product, version: ProductVersion, query: ParsedQuery, language: str
    ) -> SearchItem:
        title = name_of(version, language)
        return SearchItem(
            kind=self.kind,
            id=product.key,
            title=title,
            url_ref=f"/marketplace/products/{product.key}",
            snippet=snippet(title, query.terms),
            facets={"type": product.type},
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not query.normalized or not await self.authorizer.is_allowed(principal, READ):
            return ProviderResult()
        rows = await self.catalog.listing(q=query.text, limit=200)
        items = [self._item(p, v, query, ctx.language) for p, v in rows[:limit]]
        return ProviderResult(items=items, took_ms=int((time.perf_counter() - started) * 1000))

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        if not await self.authorizer.is_allowed(principal, READ):
            return []
        empty = ParsedQuery(text="", normalized="", terms=())
        wanted = set(ids)
        return [self._item(p, v, empty, "en") for p, v in await self.catalog.listing() if p.key in wanted]


FEATURED_WIDGET = WidgetDefinition(
    key="marketplace.featured",
    owner=OWNER,
    title_key="marketplace:widget.featured.title",
    description_key="marketplace:widget.featured.description",
    icon="sparkles",
    required_permission=READ,
    size=SizeLimits(default=Size(4, 3), min=Size(3, 1), max=Size(8, 6)),
    refresh=Refresh(mode="interval", interval_s=1800),
    stale_after_s=3600,
    component_id="marketplace.featured",
)


class FeaturedWidget:
    """``marketplace.featured`` (027 redesign): the shop window — featured products first, then the
    newest, never one the viewer already owns; with rarity, price and how many are left."""

    def __init__(self, catalog: Catalog, clock: Clock | None = None) -> None:
        self.catalog = catalog
        self.clock = clock

    async def _owned(self, user: UUID | None) -> set[UUID]:
        if user is None:
            return set()
        async with self.catalog.database.session() as session:
            rows = await session.scalars(
                select(Ownership.product_id).where(
                    Ownership.user_id == user, Ownership.state.in_(("active", "needs_configuration"))
                )
            )
            return set(rows)

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        owned = await self._owned(principal.acting_for or principal.user_id)
        rows = [
            (p, v)
            for p, v in await self.catalog.listing()
            if p.id not in owned and p.type != "project_launch"
        ]
        if not rows:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        rows.sort(key=lambda row: (not row[0].featured, -row[0].created_at.timestamp()))
        return WidgetPayload(
            "available",
            as_of=utc_now(self.clock),
            data={
                "total": len(rows),
                "items": [
                    {
                        "key": p.key,
                        "name": name_of(v, ctx.language),
                        "type": p.type,
                        "rarity": p.rarity,
                        "icon": p.icon,
                        "featured": p.featured,
                        "price": v.price_coins,
                    }
                    for p, v in rows[:6]
                ],
            },
        )


# #347: « My reserve » on the dashboard — what waits there, by the reserve page's sections
RESERVE_WIDGET = WidgetDefinition(
    key="marketplace.reserve",
    owner=OWNER,
    title_key="marketplace:widget.reserve.title",
    description_key="marketplace:widget.reserve.description",
    icon="potion",
    required_permission=READ,
    size=SizeLimits(default=Size(4, 3), min=Size(3, 1), max=Size(8, 5)),
    refresh=Refresh(mode="interval", interval_s=600),
    stale_after_s=1800,
    component_id="marketplace.reserve",
)
RESERVE_TILES = 8  # what the largest block shows; the counts say the rest
WAITING = {"needs_configuration": "todo", "locked": "waiting"}


class ReserveWidget:
    """#347: ``marketplace.reserve`` — how many things wait in the member's reserve, by its page's sections
    (to complete, to open, to use, waiting for their level), the first ones as tiles (identical ones stacked,
    how many on them), and what came in since they last opened it (#300)."""

    def __init__(self, database: Database, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        if user is None:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        async with self.database.session() as session:
            seen = await session.scalar(select(ReserveSeen.seen_at).where(ReserveSeen.user_id == user))
            held = (
                await session.execute(
                    select(Product, ProductVersion, ReserveItem.quantity, ReserveItem.received_at)
                    .join(ReserveItem, ReserveItem.product_id == Product.id)
                    .join(
                        ProductVersion,
                        (ProductVersion.product_id == Product.id)
                        & (ProductVersion.version == Product.current_version),
                    )
                    .where(ReserveItem.user_id == user, ReserveItem.quantity > 0)
                    .order_by(Product.key)
                )
            ).all()
            # a purchase waiting for its form, an item waiting for its level: the reserve page's too
            waiting = (
                await session.execute(
                    select(Ownership.state, Product, ProductVersion)
                    .join(Product, Product.id == Ownership.product_id)
                    .join(
                        ProductVersion,
                        (ProductVersion.product_id == Ownership.product_id)
                        & (ProductVersion.version == Ownership.product_version),
                    )
                    .where(Ownership.user_id == user, Ownership.state.in_(tuple(WAITING)))
                    .order_by(Ownership.acquired_at.desc(), Ownership.id)
                )
            ).all()
        counts = {"todo": 0, "open": 0, "use": 0, "waiting": 0}
        tiles: dict[tuple[str, str], dict[str, Any]] = {}

        def tile(section: str, product: Product, version: ProductVersion, quantity: int, new: bool) -> None:
            counts[section] += quantity
            found = tiles.get((section, product.key))
            if found is not None:  # identical ones stacked
                found["quantity"] += quantity
                return
            tiles[(section, product.key)] = {
                "key": product.key,
                "name": name_of(version, ctx.language),
                "type": product.type,
                "rarity": product.rarity,
                "icon": product.icon,
                "quantity": quantity,
                "section": section,
                "new": new,
            }

        for state, product, version in waiting:
            tile(WAITING[state], product, version, 1, False)
        new = 0
        for product, version, quantity, received in held:
            # as the navigation's badge counts them (Openings.unseen): never opened, or come in since
            fresh = seen is None or (received is not None and received > seen)
            new += int(fresh)
            tile("open" if product.type == "booster" else "use", product, version, int(quantity), fresh)
        if not tiles:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        order = ("todo", "open", "use", "waiting")  # the reserve page's
        items = sorted(tiles.values(), key=lambda item: order.index(item["section"]))
        return WidgetPayload(
            "available",
            as_of=utc_now(self.clock),
            data={"counts": counts, "new": new, "items": items[:RESERVE_TILES]},
        )


def catalog_tool(catalog: Catalog, clock: Clock | None = None) -> AITool:
    async def handler(principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        rows = await catalog.listing(q=str(params.get("query") or "") or None, limit=20)
        return ToolResult(
            "ok",
            {
                "products": [
                    {"key": p.key, "name": name_of(v), "type": p.type, "price_coins": v.price_coins}
                    for p, v in rows[:20]
                ]
            },
            (
                SourceRef(
                    "marketplace",
                    "marketplace:catalog",
                    "Marketplace",
                    "real",
                    utc_now(clock),
                    "/marketplace",
                ),
            ),
        )

    return AITool(
        name="marketplace.catalog",
        description="Products available in the Marketplace (name, type, price in Coins). Read-only.",
        params_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "maxLength": 64}},
            "additionalProperties": False,
        },
        required_permission=READ,
        sensitivity="read",
        handler=handler,
        owner=OWNER,
    )


def cosmetics_section(entitlements: Entitlements) -> ProfileSection:
    async def provider(owner: UUID, viewer: Principal) -> SectionResult:
        badges = await entitlements.owned_items(owner, "badge")
        titles = await entitlements.owned_items(owner, "title")
        if not badges and not titles:
            return SectionResult("no-data")
        return SectionResult("available", {"badges": badges, "titles": titles})

    return ProfileSection(
        "cosmetics", OWNER, "progression", provider, 60, label_key="marketplace:section.cosmetics"
    )
