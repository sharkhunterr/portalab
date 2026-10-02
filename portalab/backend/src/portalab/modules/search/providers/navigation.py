"""Navigation destinations provider (T015): the 004 navigation entries the principal may open, matched on
their localized label and keywords. Each entry keeps its own required permission."""

import asyncio
import time
from collections.abc import Sequence

from portalab.capabilities.i18n import LocaleContext, normalize_for_search
from portalab.capabilities.navigation import NavigationContribution, NavigationRegistry, default_navigation
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet
from portalab.core.authz_port import Authorizer, Principal
from portalab.modules.search.permissions import SEARCH_USE
from portalab.modules.search.providers.common import Labels


class NavigationProvider:
    kind = "navigation"
    label_key = "search.kind.navigation"
    required_permission = SEARCH_USE

    def __init__(
        self,
        authorizer: Authorizer,
        capabilities: CapabilityRegistry,
        registry: NavigationRegistry = default_navigation,
    ) -> None:
        self.authorizer = authorizer
        self.registry = registry
        self.labels = Labels(capabilities)

    def facets(self) -> Sequence[FacetDef]:
        return ()

    async def _entries(self, principal: Principal) -> list[NavigationContribution]:
        entries = [c for c in self.registry.all() if c.kind == "entry" and c.route]
        allowed = await asyncio.gather(
            *(self.authorizer.is_allowed(principal, entry.required_permission) for entry in entries)
        )
        return [entry for entry, ok in zip(entries, allowed, strict=True) if ok]

    def _item(
        self, entry: NavigationContribution, ctx: LocaleContext, query: ParsedQuery, score: float
    ) -> SearchItem:
        title = self.labels(entry.label_key, ctx)
        return SearchItem(
            kind=self.kind,
            id=entry.key,
            title=title,
            url_ref=entry.route or "/",
            snippet=snippet(title, query.terms),
            score=score,
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        scored: list[tuple[float, NavigationContribution]] = []
        for entry in await self._entries(principal):
            haystack = normalize_for_search(
                " ".join((self.labels(entry.label_key, ctx), *entry.keywords, entry.key)), ctx.language
            )
            if not query.normalized:
                continue
            hits = sum(1 for term in query.terms if term in haystack)
            if hits:
                scored.append((hits / max(1, len(query.terms)), entry))
        scored.sort(key=lambda pair: (-pair[0], pair[1].order_hint, pair[1].key))
        offset = decode_cursor(cursor)
        page = scored[offset : offset + limit]
        return ProviderResult(
            items=[self._item(entry, ctx, query, score) for score, entry in page],
            next_cursor=encode_cursor(offset + limit) if offset + limit < len(scored) else None,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        allowed = {entry.key: entry for entry in await self._entries(principal)}
        ctx = LocaleContext()
        empty = ParsedQuery(text="", normalized="", terms=())
        return [self._item(allowed[i], ctx, empty, 0.0) for i in ids if i in allowed]
