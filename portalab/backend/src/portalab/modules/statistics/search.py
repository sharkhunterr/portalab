"""Statistics search provider (spec 008 FR-012, #84): the statistics a member can open — « what I finished »,
« my visits », « votes cast » — matched on their title and description in the member's language (026
renderer; the keys themselves when i18n is not installed). Only the viewer's own catalog is searched, so a
statistic their permissions do not reach is never found; a locked one is found as the catalog shows it
(locked, no value). Filterable by domain."""

import time
from collections.abc import Sequence
from typing import Any

from portalab.capabilities.i18n import RENDERER, LocaleContext, normalize_for_search
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet
from portalab.capabilities.statistics import CatalogEntry
from portalab.core.authz_port import Authorizer, Principal
from portalab.modules.statistics.permissions import STATISTICS_READ
from portalab.modules.statistics.provider.provider import Provider


class StatisticsSearchProvider:
    kind = "statistics"
    label_key = "search.kind.statistics"
    required_permission = STATISTICS_READ

    def __init__(self, provider: Provider, authorizer: Authorizer, capabilities: CapabilityRegistry) -> None:
        self.provider = provider
        self.authorizer = authorizer
        self.capabilities = capabilities

    def facets(self) -> Sequence[FacetDef]:
        return (FacetDef("domain", "search.facet.domain"),)

    def _text(self, key: str | None, ctx: LocaleContext) -> str:
        if not key:
            return ""
        namespace, separator, message = key.partition(":")
        if not separator:
            namespace, message = "statistics", key
        try:
            providers = self.capabilities.system_providers(RENDERER)
            if not providers:
                return key  # i18n not installed: the key is still something to match and show
            renderer: Any = providers[0].provider
            return str(renderer.t(message, ctx, namespace=namespace))
        except Exception:
            return key

    async def _catalog(self, principal: Principal) -> list[CatalogEntry]:
        if not await self.authorizer.is_allowed(principal, STATISTICS_READ):
            return []  # scoped at source too, not only by the coordinator
        return list(await self.provider.catalog(principal))

    def _item(self, entry: CatalogEntry, title: str, description: str, query: ParsedQuery) -> SearchItem:
        return SearchItem(
            kind=self.kind,
            id=entry.key,
            title=title,
            url_ref=f"/statistics#{entry.key}",
            snippet=snippet(description, query.terms) if description else (),
            facets={
                "domain": entry.domain,
                "scope": entry.scope,
                "state": "locked" if entry.locked else "open",
            },
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not query.terms:
            return ProviderResult()
        wanted = query.filters.get("domain")
        matches: list[SearchItem] = []
        for entry in await self._catalog(principal):
            if wanted and entry.domain not in wanted:
                continue
            title, description = self._text(entry.title_key, ctx), self._text(entry.description_key, ctx)
            haystack = normalize_for_search(f"{title} {description}", ctx.language)
            if all(term in haystack for term in query.terms):
                matches.append(self._item(entry, title, description, query))
        counts: dict[str, int] = {}
        for item in matches:
            counts[item.facets["domain"]] = counts.get(item.facets["domain"], 0) + 1
        offset = decode_cursor(cursor)
        return ProviderResult(
            items=matches[offset : offset + limit],
            next_cursor=encode_cursor(offset + limit) if offset + limit < len(matches) else None,
            facets={"domain": counts},
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        wanted = set(ids)
        empty = ParsedQuery(text="", normalized="", terms=())
        ctx = LocaleContext()
        return [
            self._item(e, self._text(e.title_key, ctx), self._text(e.description_key, ctx), empty)
            for e in await self._catalog(principal)
            if e.key in wanted
        ]
