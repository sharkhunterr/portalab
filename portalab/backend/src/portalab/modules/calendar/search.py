"""Calendar search provider (spec 008 FR-012, #84): what is on the calendar — portal events, maintenance,
publications, media releases — from a week ago to the end of the calendar's range, for principals holding
``calendar.read``. Items come through the ``CalendarAggregator``, so every source applies its own permission
and audience **at source** (a role-only event never reaches someone outside the role); matched on the title
and its finer kind, the coming ones first; filterable by source."""

import time
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from portalab.capabilities.content import CalendarItem
from portalab.capabilities.i18n import LocaleContext, normalize_for_search
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.calendar.aggregator import CalendarAggregator, CalendarView, when
from portalab.modules.calendar.permissions import CALENDAR_READ
from portalab.modules.calendar.settings import CalendarConfig

PAST = timedelta(days=7)  # what just happened is still looked for (« the maintenance last Tuesday »)


def item_id(item: CalendarItem) -> str:
    return f"{item.source_kind}:{item.source_id}"


class CalendarSearchProvider:
    kind = "calendar"
    label_key = "search.kind.calendar"
    required_permission = CALENDAR_READ

    def __init__(
        self,
        aggregator: CalendarAggregator,
        authorizer: Authorizer,
        config: Callable[[], CalendarConfig],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.aggregator = aggregator
        self.authorizer = authorizer
        self.config = config
        self.clock = clock

    def facets(self) -> Sequence[FacetDef]:
        return (FacetDef("source", "search.facet.source"),)

    async def _view(self, principal: Principal, ctx: LocaleContext) -> tuple[CalendarView, datetime] | None:
        if not await self.authorizer.is_allowed(principal, CALENDAR_READ):
            return None  # scoped at source too, not only by the coordinator
        now = utc_now(self.clock)
        start = now - PAST
        end = start + timedelta(days=max(1, self.config().max_range_days))
        return await self.aggregator.view(principal, start, end, ctx), now

    def _item(self, item: CalendarItem, query: ParsedQuery) -> SearchItem:
        day = item.date.isoformat() if item.date else item.starts_at.isoformat() if item.starts_at else ""
        route = item.url_ref if item.url_ref and item.url_ref.startswith("/") else "/calendar"
        return SearchItem(
            kind=self.kind,
            id=item_id(item),
            title=item.title,
            url_ref=route,
            snippet=snippet(item.title, query.terms),
            facets={"source": item.source_kind, "status": item.status, "when": day},
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        seen = await self._view(principal, ctx) if query.terms else None
        if seen is None:
            return ProviderResult()
        view, now = seen
        wanted = query.filters.get("source")
        matches = [
            item
            for item in view.items
            if (not wanted or item.source_kind in wanted)
            and all(
                term in normalize_for_search(f"{item.title} {item.category or ''}", ctx.language)
                for term in query.terms
            )
        ]
        # the coming ones first (soonest first), then what just happened (latest first)
        matches.sort(key=lambda i: (when(i, now) < now, abs((when(i, now) - now).total_seconds())))
        counts: dict[str, int] = {}
        for item in matches:
            counts[item.source_kind] = counts.get(item.source_kind, 0) + 1
        offset = decode_cursor(cursor)
        page = matches[offset : offset + limit]
        return ProviderResult(
            items=[self._item(item, query) for item in page],
            state="ok" if all(s == "ok" for s in view.source_states.values()) else "partial",
            next_cursor=encode_cursor(offset + limit) if offset + limit < len(matches) else None,
            facets={"source": counts},
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        seen = await self._view(principal, LocaleContext())
        if seen is None:
            return []
        wanted = set(ids)
        empty = ParsedQuery(text="", normalized="", terms=())
        return [self._item(item, empty) for item in seen[0].items if item_id(item) in wanted]
