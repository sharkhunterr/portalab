"""Incident integrations (T012): the dashboard widget ``support.open_incidents`` (009 SDK) and the search
provider ``incidents`` (008 SDK). Both use the same visibility rule as the API: ``incidents.read``; the
affected services are only named to holders of ``services.read``."""

import time
from collections.abc import Mapping, Sequence
from typing import Any

from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.i18n import LocaleContext, normalize_for_search
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.support.incidents.service import IncidentNotFound, IncidentService, IncidentView
from portalab.modules.support.permissions import INCIDENTS_READ

OPEN_INCIDENTS = WidgetDefinition(
    key="support.open_incidents",
    owner="module:support",
    title_key="support:widget.incidents.title",
    description_key="support:widget.incidents.description",
    icon="alert",
    required_permission=INCIDENTS_READ,
    size=SizeLimits(default=Size(6, 2), min=Size(3, 2), max=Size(12, 6)),
    refresh=Refresh(mode="event", events=("incident.created", "incident.updated", "incident.resolved")),
    stale_after_s=900,
    template="list",
)


class OpenIncidentsWidget:
    def __init__(self, incidents: IncidentService, clock: Clock | None = None) -> None:
        self.incidents = incidents
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        views = await self.incidents.list(state="open", limit=10)
        if not views:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        items = [
            {
                "title": f"{v.reference} · {v.title}",
                "route": f"/incidents/{v.id}",
                "meta": f"{v.severity} · {v.state}",
            }
            for v in views
        ]
        return WidgetPayload("available", as_of=utc_now(self.clock), data={"items": items})


class IncidentSearchProvider:
    kind = "incidents"
    label_key = "search.kind.incidents"
    required_permission = INCIDENTS_READ

    def __init__(self, incidents: IncidentService, authorizer: Authorizer) -> None:
        self.incidents = incidents
        self.authorizer = authorizer

    def facets(self) -> Sequence[FacetDef]:
        return (
            FacetDef(
                "state",
                "search.facet.state",
                values=("investigating", "identified", "monitoring", "resolved"),
            ),
            FacetDef("severity", "search.facet.severity", values=("minor", "major", "critical")),
        )

    def _item(self, view: IncidentView, query: ParsedQuery, score: float = 0.0) -> SearchItem:
        return SearchItem(
            kind=self.kind,
            id=str(view.id),
            title=f"{view.reference} · {view.title}",
            url_ref=f"/incidents/{view.id}",
            snippet=snippet(view.summary or view.title, query.terms),
            score=score,
            facets={"state": view.state, "severity": view.severity},
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not await self.authorizer.is_allowed(principal, INCIDENTS_READ):
            return ProviderResult()
        matches: list[tuple[float, IncidentView]] = []
        for view in await self.incidents.list(limit=500):
            if any(getattr(view, name) not in values for name, values in query.filters.items()):
                continue
            haystack = normalize_for_search(f"{view.reference} {view.title} {view.summary}", ctx.language)
            hits = sum(1 for term in query.terms if term in haystack) if query.terms else 1
            if hits:
                matches.append((hits / max(1, len(query.terms)), view))
        matches.sort(key=lambda pair: (-pair[0], -pair[1].created_at.timestamp()))
        facets: dict[str, dict[str, int]] = {"state": {}, "severity": {}}
        for _, view in matches:
            facets["state"][view.state] = facets["state"].get(view.state, 0) + 1
            facets["severity"][view.severity] = facets["severity"].get(view.severity, 0) + 1
        offset = decode_cursor(cursor)
        page = matches[offset : offset + limit]
        return ProviderResult(
            items=[self._item(view, query, score) for score, view in page],
            next_cursor=encode_cursor(offset + limit) if offset + limit < len(matches) else None,
            facets=facets,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        from uuid import UUID

        if not await self.authorizer.is_allowed(principal, INCIDENTS_READ):
            return []
        empty = ParsedQuery(text="", normalized="", terms=())
        out = []
        for value in ids:
            try:
                out.append(self._item(await self.incidents.get(UUID(value)), empty))
            except (ValueError, IncidentNotFound):
                continue
        return out
