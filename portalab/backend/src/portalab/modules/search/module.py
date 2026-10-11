"""Search module facade (spec 008): federated search, history, assist gateway, palette backend, semantic
index and administration."""

import asyncio
import threading
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.i18n import RESOLVER, LocaleContext
from portalab.capabilities.navigation import NavigationRegistry, default_navigation
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.capabilities.search import Mode, SearchRegistry, default_search
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Authorizer, Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import PortalError
from portalab.core.event_port import EventPublisher
from portalab.core.ids import new_id
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.queue import enqueue
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock, utc_now
from portalab.modules.search import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.search.assist.gateway import AssistGateway
from portalab.modules.search.coordinator.coordinator import SearchCoordinator, SearchOutcome
from portalab.modules.search.events import SearchEvents, register_event_types
from portalab.modules.search.history.service import HistoryParticipant, HistoryService
from portalab.modules.search.observability import metrics
from portalab.modules.search.palette.resolver import PaletteResolution, PaletteResolver
from portalab.modules.search.parser.parser import QueryParser
from portalab.modules.search.providers.navigation import NavigationProvider
from portalab.modules.search.providers.services import ServicesProvider
from portalab.modules.search.semantic.index import SemanticIndex
from portalab.modules.search.settings import SearchConfig

OWNER = "module:search"
INDEX_JOB = "search.index"
PURGE_JOB = "search.history_purge"


class RateLimited(PortalError):
    status = 429
    default_code = "search.rate_limited"
    default_title = "Too many searches"


class UserLimiter:
    """Per-user sliding window (single node, like the kernel limiter)."""

    def __init__(self, window: float = 60.0) -> None:
        self.window = window
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int) -> float | None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= max(1, limit):
                return max(0.0, hits[0] + self.window - now)
            hits.append(now)
            if len(self._hits) > 50_000:
                for stale in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
                    del self._hits[stale]
            return None


@dataclass(frozen=True, slots=True)
class SearchRequest:
    q: str
    mode: Mode = "mixed"
    filters: Mapping[str, Sequence[str]] | None = None
    kinds: Sequence[str] | None = None
    cursor: str | None = None


def _varied(items: Sequence[Any], each: int = 4, media: int = 6) -> list[Any]:
    """#67: a source's first suggestions — for media, taken in turn from each type (films, series, books,
    games…) in their relevance order, so one type never fills every place."""
    if not items or items[0].kind != "media":
        return list(items[:each])
    by_type: dict[str, list[Any]] = {}
    for item in items:
        by_type.setdefault(str(item.facets.get("type", "")), []).append(item)
    out: list[Any] = []
    while len(out) < media and any(by_type.values()):
        for queue in by_type.values():
            if queue and len(out) < media:
                out.append(queue.pop(0))
    return out


class SearchModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        registry: SearchRegistry = default_search,
        navigation: NavigationRegistry = default_navigation,
        event_types: EventTypeRegistry = default_event_types,
        observables: ObservableRegistry = default_observables,
    ) -> None:
        self.database = database
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.registry = registry
        self.navigation = navigation
        self.config = SearchConfig()
        self.semantic = SemanticIndex(database, capabilities, registry, clock=clock)
        self.search_events = SearchEvents(database, events)
        self.coordinator = SearchCoordinator(
            registry,
            authorizer,
            lambda: self.config,
            semantic=self.semantic.candidates,
            semantic_available=self.semantic.available,
            on_failure=self._provider_failed,
        )
        self.history = HistoryService(database, capabilities, lambda: self.config, clock=clock)
        self.assist = AssistGateway(capabilities, self.coordinator)
        self.palette = PaletteResolver(registry, authorizer, capabilities, self.coordinator, navigation)
        self.limiter = UserLimiter()
        self.event_types = event_types
        self.observables = observables
        self._pending: set[asyncio.Task[None]] = set()

    def register(self) -> None:
        self.registry.register(
            NavigationProvider(self.authorizer, self.capabilities, self.navigation), owner=OWNER
        )
        self.registry.register(ServicesProvider(self.capabilities, self.authorizer), owner=OWNER)
        register_event_types(self.event_types)
        participant = HistoryParticipant(self.history)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(
                p.instance_ref == "search.history" for p in self.capabilities.system_providers(capability)
            ):
                self.capabilities.provide(capability, participant, instance_ref="search.history", owner=OWNER)
        default_retention_targets.register(
            RetentionTarget(
                "search.history",
                "search.history",
                "activity",
                "performed_at",
                "delete",
                OWNER,
                window=lambda: timedelta(days=max(1, self.config.history_retention_days)),
            )
        )
        self.observables.declare(
            ObservedComponent(
                "search", OWNER, label="Search", functional_checks=(Check("providers", self.probe),)
            )
        )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def index(payload: dict[str, Any]) -> None:
            await self.semantic.index(str(payload["kind"]), full=bool(payload.get("full")))

        jobs.register(
            INDEX_JOB, index, idempotency="content-hash skip; upsert per (kind, id, language)", owner=OWNER
        )
        purge = register_periodic(
            jobs, self.database, PURGE_JOB, timedelta(days=1), self.history.purge_expired, owner=OWNER
        )
        return [purge]

    # --- search --------------------------------------------------------------------------------------
    async def locale(self, principal: Principal) -> LocaleContext:
        providers = self.capabilities.system_providers(RESOLVER)
        if not providers:
            return LocaleContext()
        try:
            ctx = await providers[0].provider.for_user(principal.user_id)
        except Exception:
            return LocaleContext()
        return ctx if isinstance(ctx, LocaleContext) else LocaleContext()

    def limit(self, principal: Principal) -> None:
        key = str(principal.user_id or principal.acting_for or "anonymous")
        wait = self.limiter.hit(key, self.config.rate_limit_per_minute)
        if wait is not None:
            metrics.increment("search.rate_limited")
            raise RateLimited(
                "Too many searches; try again in a moment.", extensions={"retry_after": int(wait) + 1}
            )

    async def search(self, principal: Principal, request: SearchRequest) -> tuple[SearchOutcome, str]:
        self.limit(principal)
        ctx = await self.locale(principal)
        parser = QueryParser(max_length=self.config.max_query_length)
        query = parser.parse(
            request.q,
            ctx,
            now=utc_now(self.clock),
            mode=request.mode,
            filters=request.filters,
            kinds=request.kinds,
        )
        outcome = await self.coordinator.search(query, principal, ctx, cursor=request.cursor)
        request_id = str(new_id())
        if principal.user_id is not None and request.cursor is None:
            self._background(self.history.record(principal.user_id, query, request.q))
        self._background(
            self.search_events.performed(
                principal,
                request_id,
                {group.kind: len(group.items) for group in outcome.groups},
                outcome.took_ms,
                query.mode,
                outcome.semantic,
                utc_now(self.clock),
            )
        )
        return outcome, request_id

    async def suggest(self, principal: Principal, q: str) -> list[dict[str, Any]]:
        """Typeahead: the first matches of each permitted kind (same scoping as ``search``) — 027: with a
        line of context and the item's facets, for the header's live results."""
        outcome, _ = await self.search_without_side_effects(principal, q)
        return [
            {
                "kind": item.kind,
                "id": item.id,
                "title": item.title,
                "url_ref": item.url_ref,
                "snippet": "".join(segment.text for segment in item.snippet)[:160],
                "facets": dict(item.facets),
                "group": group.label_key,  # the provider's own label for its kind
            }
            for group in outcome.groups
            for item in _varied(group.items)
        ][:20]

    async def search_without_side_effects(self, principal: Principal, q: str) -> tuple[SearchOutcome, str]:
        self.limit(principal)
        ctx = await self.locale(principal)
        query = QueryParser(max_length=self.config.max_query_length).parse(
            q, ctx, now=utc_now(self.clock), mode="exact"
        )
        return await self.coordinator.search(query, principal, ctx), ""

    async def resolve_palette(self, principal: Principal, q: str, route: str | None) -> PaletteResolution:
        return await self.palette.resolve(q, principal, await self.locale(principal), route)

    def _background(self, coroutine: Any) -> None:
        task = asyncio.ensure_future(coroutine)
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def drain(self) -> None:
        """Await background side effects (history, usage event) — tests and shutdown."""
        while self._pending:
            await asyncio.gather(*list(self._pending), return_exceptions=True)

    async def _provider_failed(self, kind: str, reason: str) -> None:
        self._background(self.search_events.provider_failed(kind, reason, utc_now(self.clock)))

    # --- administration ------------------------------------------------------------------------------
    async def reindex(self, principal: Principal, kinds: Sequence[str] | None) -> list[str]:
        targets = [p.kind for p in self.registry.providers(kinds)]
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            for kind in targets:
                await enqueue(
                    uow.session,
                    kind=INDEX_JOB,
                    payload={"kind": kind, "full": True},
                    dedup_key=f"{INDEX_JOB}:{kind}:{now.strftime('%Y%m%dT%H%M')}",
                    clock=self.clock,
                )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="search.reindex",
                    actor=principal,
                    resource=ResourceRef("search_index", ",".join(targets) or "none"),
                    decision="allow",
                    result="success",
                    context={"kinds": targets},
                    sensitive=True,
                ),
            )
        return targets

    async def status(self) -> dict[str, Any]:
        return {
            "providers": [
                {"kind": p.kind, "label_key": p.label_key, "required_permission": p.required_permission}
                for p in self.registry.providers()
            ],
            "semantic": {
                "enabled": self.config.semantic_enabled,
                "available": await self.semantic.available(),
                "pgvector": await self.semantic.table_exists(),
            },
            "index": await self.semantic.status(),
            "metrics": metrics.snapshot(),
        }

    async def probe(self) -> CheckResult:
        """Functional check (025): every provider answers a representative query within its budget."""
        system = Principal(user_id=UUID(int=0))
        query = QueryParser().parse("portalab", LocaleContext(), now=utc_now(self.clock), mode="exact")
        failing = []
        for provider in self.registry.providers():
            try:
                await asyncio.wait_for(
                    provider.search(query, system, LocaleContext(), limit=1, cursor=None),
                    timeout=self.config.provider_timeout_ms / 1000,
                )
            except Exception:
                failing.append(provider.kind)
        facts = {"providers": len(self.registry.providers()), "failing": len(failing)}
        if failing:
            return CheckResult("degraded", f"{len(failing)} search source(s) failing", facts)
        return CheckResult("ok", "all search sources answer", facts)
