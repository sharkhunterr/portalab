"""Integrations (T020, T033): the ``product`` search provider (008, ``marketplace.read``), the dashboard
widget ``marketplace.featured`` (009), the read-only AI tool ``marketplace.catalog`` (018) and the
``cosmetics`` profile section (012: owned badges and titles, under the owner's ``progression``
visibility)."""

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
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.entitlements.reader import Entitlements
from portalab.modules.marketplace.models import Ownership, Product, ProductVersion
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
