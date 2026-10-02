"""``SearchCoordinator`` (T010, T022; R1, R4, R13): fans a parsed query out to every *permitted* provider in
parallel, each under its own time budget, and merges grouped results.

* a kind the principal may not use is never queried and contributes nothing — no group, no count, no facet
  (FR-013, CD-002); unknown requested kinds are ignored the same way (reveal nothing);
* a slow or failing provider yields its own ``unavailable`` group; the others are unaffected (FR-014);
* semantic candidates (optional) are re-hydrated **and re-authorized** by their owning provider, so a
  stale or forbidden id is dropped (R3); without an embedding provider semantic mode is reported
  ``unavailable`` and lexical matching continues (R4);
* never raises to the caller for a provider problem.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import (
    FacetDef,
    GroupState,
    ParsedQuery,
    ProviderResult,
    SearchItem,
    SearchProvider,
    SearchRegistry,
)
from portalab.core.authz_port import Authorizer, Principal
from portalab.modules.search.observability import log, metric_part, metrics
from portalab.modules.search.parser.parser import InvalidFilter
from portalab.modules.search.settings import SearchConfig

SemanticState = Literal["ok", "unavailable", "off"]
SemanticCandidates = Callable[
    [ParsedQuery, Sequence[str], int], Awaitable[Mapping[str, Sequence[str]] | None]
]
FailureHook = Callable[[str, str], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Group:
    kind: str
    label_key: str
    state: GroupState
    items: Sequence[SearchItem] = ()
    next_cursor: str | None = None
    facets: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    facet_defs: Sequence[FacetDef] = ()
    took_ms: int = 0


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    groups: Sequence[Group]
    took_ms: int
    semantic: SemanticState
    total: int


def _declares(provider: SearchProvider, query: ParsedQuery) -> bool:
    """A provider takes part only if it understands every filter (and the date range, when one is set)."""
    defs = {facet.key: facet for facet in provider.facets()}
    if any(name not in defs for name in query.filters):
        return False
    for name, values in query.filters.items():
        allowed = defs[name].values
        if allowed and any(value not in allowed for value in values):
            raise InvalidFilter(f"invalid value for filter {name!r}", extensions={"filter": name})
    if query.date_from or query.date_to:
        return any(facet.kind == "date" for facet in defs.values())
    return True


class SearchCoordinator:
    def __init__(
        self,
        registry: SearchRegistry,
        authorizer: Authorizer,
        config: Callable[[], SearchConfig],
        *,
        semantic: SemanticCandidates | None = None,
        semantic_available: Callable[[], Awaitable[bool]] | None = None,
        on_failure: FailureHook | None = None,
    ) -> None:
        self.registry = registry
        self.authorizer = authorizer
        self.config = config
        self.semantic = semantic
        self.semantic_available = semantic_available
        self.on_failure = on_failure

    async def permitted(
        self, principal: Principal, kinds: Sequence[str] | None = None
    ) -> list[SearchProvider]:
        providers = self.registry.providers(kinds)
        allowed = await asyncio.gather(
            *(self._allowed(principal, provider.required_permission) for provider in providers)
        )
        return [provider for provider, ok in zip(providers, allowed, strict=True) if ok]

    async def _allowed(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False  # fail closed

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, cursor: str | None = None
    ) -> SearchOutcome:
        started = time.perf_counter()
        config = self.config()
        providers = await self.permitted(principal, query.kinds)
        if (
            query.filters
            and providers
            and not any(name in {f.key for p in providers for f in p.facets()} for name in query.filters)
        ):
            raise InvalidFilter("no search source supports these filters")
        providers = [provider for provider in providers if _declares(provider, query)]
        semantic_state, candidates = await self._semantic(query, [p.kind for p in providers], config)
        limit = max(1, config.max_results_per_group)
        timeout = max(0.05, config.provider_timeout_ms / 1000)
        page_cursor = cursor if len(providers) == 1 else None
        results = await asyncio.gather(
            *(
                self._run(
                    provider,
                    query,
                    principal,
                    ctx,
                    limit,
                    page_cursor,
                    timeout,
                    candidates.get(provider.kind, ()),
                )
                for provider in providers
            )
        )
        took = int((time.perf_counter() - started) * 1000)
        total = sum(len(group.items) for group in results)
        metrics.increment("search.queries")
        if total == 0:
            metrics.increment("search.zero_results")
        metrics.gauge("search.latency_ms", took)
        return SearchOutcome(groups=results, took_ms=took, semantic=semantic_state, total=total)

    async def _semantic(
        self, query: ParsedQuery, kinds: Sequence[str], config: SearchConfig
    ) -> tuple[SemanticState, Mapping[str, Sequence[str]]]:
        if query.mode == "exact" or not query.normalized:
            return "off", {}
        available = bool(
            config.semantic_enabled
            and self.semantic is not None
            and self.semantic_available is not None
            and await self.semantic_available()
        )
        if not available or self.semantic is None:
            metrics.increment("search.semantic.unavailable")
            return "unavailable", {}
        try:
            found = await asyncio.wait_for(
                self.semantic(query, kinds, config.semantic_top_k), timeout=config.provider_timeout_ms / 1000
            )
        except Exception:
            log.warning("semantic candidates unavailable")
            metrics.increment("search.semantic.failures")
            return "unavailable", {}
        return ("ok", found) if found is not None else ("unavailable", {})

    async def _run(
        self,
        provider: SearchProvider,
        query: ParsedQuery,
        principal: Principal,
        ctx: LocaleContext,
        limit: int,
        cursor: str | None,
        budget: float,
        semantic_ids: Sequence[str],
    ) -> Group:
        started = time.perf_counter()
        kind = provider.kind
        try:
            result: ProviderResult = await asyncio.wait_for(
                provider.search(query, principal, ctx, limit=limit, cursor=cursor), timeout=budget
            )
            items = list(result.items)[:limit]
            if semantic_ids and query.mode != "exact":
                items = await self._merge_semantic(provider, principal, items, semantic_ids, limit, budget)
            state: GroupState = result.state
            next_cursor, facets = result.next_cursor, result.facets
        except TimeoutError:
            await self._failed(kind, "timeout")
            return Group(kind, provider.label_key, "unavailable", facet_defs=tuple(provider.facets()))
        except InvalidFilter:
            raise
        except Exception:
            log.warning("search provider failed", extra={"kind": kind})
            await self._failed(kind, "error")
            return Group(kind, provider.label_key, "unavailable", facet_defs=tuple(provider.facets()))
        took = int((time.perf_counter() - started) * 1000)
        metrics.gauge(f"search.provider.{metric_part(kind)}.latency_ms", took)
        return Group(
            kind,
            provider.label_key,
            state,
            items=tuple(items),
            next_cursor=next_cursor,
            facets=facets,
            facet_defs=tuple(provider.facets()),
            took_ms=took,
        )

    async def _merge_semantic(
        self,
        provider: SearchProvider,
        principal: Principal,
        items: list[SearchItem],
        ids: Sequence[str],
        limit: int,
        budget: float,
    ) -> list[SearchItem]:
        seen = {item.id for item in items}
        wanted = [i for i in ids if i not in seen]
        if not wanted or len(items) >= limit:
            return items
        hydrated = await asyncio.wait_for(provider.hydrate(wanted, principal), timeout=budget)
        by_id = {item.id: item for item in hydrated}  # forbidden or deleted ids are simply absent
        extra: list[Any] = [by_id[i] for i in wanted if i in by_id]
        return items + [replace(item, matched_by="semantic") for item in extra][: limit - len(items)]

    async def _failed(self, kind: str, reason: str) -> None:
        metrics.increment(f"search.provider.{metric_part(kind)}.{reason}")
        if self.on_failure is not None:
            try:
                await self.on_failure(kind, reason)
            except Exception:
                log.warning("search failure hook failed")
