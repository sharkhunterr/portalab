"""Services provider (T015): the services configured in Connectors (005), for principals holding
``services.read``; matched on name and connector, filterable by connection state and connector. The
directory is read through the ``connectors.directory`` capability — never another module's tables."""

import time
from collections.abc import Sequence
from typing import Any

from portalab.capabilities.health import SERVICE_DIRECTORY, ServiceInfo
from portalab.capabilities.i18n import LocaleContext, normalize_for_search
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet
from portalab.core.authz_port import Authorizer, Principal

SERVICES_READ = "services.read"


class ServicesProvider:
    kind = "services"
    label_key = "search.kind.services"
    required_permission = SERVICES_READ

    def __init__(self, capabilities: CapabilityRegistry, authorizer: Authorizer) -> None:
        self.capabilities = capabilities
        self.authorizer = authorizer

    def facets(self) -> Sequence[FacetDef]:
        return (
            FacetDef("state", "search.facet.state"),
            FacetDef("connector", "search.facet.connector"),
        )

    async def _all(self, principal: Principal) -> list[ServiceInfo]:
        if not await self.authorizer.is_allowed(principal, SERVICES_READ):
            return []  # scoped at source too, not only by the coordinator
        providers = self.capabilities.system_providers(SERVICE_DIRECTORY)
        if not providers:
            raise LookupError("service directory unavailable")
        directory: Any = providers[0].provider
        return list(await directory.services())

    def _item(self, service: ServiceInfo, query: ParsedQuery, score: float = 0.0) -> SearchItem:
        return SearchItem(
            kind=self.kind,
            id=service.id,
            title=service.name,
            url_ref=f"/services/{service.id}",
            snippet=snippet(f"{service.name} · {service.connector}", query.terms),
            score=score,
            facets={"state": service.state, "connector": service.connector},
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        matches: list[tuple[float, ServiceInfo]] = []
        for service in await self._all(principal):
            if any(getattr(service, name, None) not in values for name, values in query.filters.items()):
                continue
            haystack = normalize_for_search(f"{service.name} {service.connector}", ctx.language)
            hits = sum(1 for term in query.terms if term in haystack) if query.terms else 1
            if hits:
                matches.append((hits / max(1, len(query.terms)), service))
        matches.sort(key=lambda pair: (-pair[0], pair[1].name.casefold()))
        facets: dict[str, dict[str, int]] = {"state": {}, "connector": {}}
        for _, service in matches:
            facets["state"][service.state] = facets["state"].get(service.state, 0) + 1
            facets["connector"][service.connector] = facets["connector"].get(service.connector, 0) + 1
        offset = decode_cursor(cursor)
        page = matches[offset : offset + limit]
        return ProviderResult(
            items=[self._item(service, query, score) for score, service in page],
            next_cursor=encode_cursor(offset + limit) if offset + limit < len(matches) else None,
            facets=facets,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        wanted = set(ids)
        empty = ParsedQuery(text="", normalized="", terms=())
        return [self._item(s, empty) for s in await self._all(principal) if s.id in wanted]
