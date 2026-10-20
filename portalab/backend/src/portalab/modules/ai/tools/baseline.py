"""Baseline read tools (T021, T025): thin wrappers over the **existing** ports of 008 (search), 011 (wiki
knowledge, contextual help), 006 (service state), 017 (statistics) and 004 (navigation). Each runs as the
AI principal acting for the user — the wrapped services apply their own permission rules, so the assistant
never sees more than the user. Domain modules may register richer tools of their own."""

import asyncio
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from portalab.capabilities.ai import AITool, AIToolRegistry, ResultState, SourceRef, ToolResult
from portalab.capabilities.content import HELP, KNOWLEDGE
from portalab.capabilities.health import SERVICE_DIRECTORY, SERVICE_STATE
from portalab.capabilities.i18n import DEFAULT_CONTEXT, normalize_for_search
from portalab.capabilities.navigation import NavigationRegistry, default_navigation
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import ParsedQuery, SearchRegistry, default_search
from portalab.capabilities.statistics import PROVIDER as STATISTICS
from portalab.capabilities.statistics import Period
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.time import Clock, utc_now

OWNER = "module:ai"
PORT_TIMEOUT = 4.0
OPERATIONAL = ("operational",)
_QUERY = {
    "type": "object",
    "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 200}},
    "required": ["query"],
    "additionalProperties": False,
}
_STAT_STATES: dict[str, ResultState] = {"available": "ok", "partial": "partial", "stale": "stale"}


class BaselineTools:
    def __init__(
        self,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        search: SearchRegistry = default_search,
        navigation: NavigationRegistry = default_navigation,
        clock: Clock | None = None,
    ) -> None:
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.search_registry = search
        self.navigation = navigation
        self.clock = clock

    def _port(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def _allowed(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False

    # --- 008 global search ------------------------------------------------------------------------------
    async def search(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        text = str(params["query"])
        normalized = normalize_for_search(text, None)
        query = ParsedQuery(text=text, normalized=normalized, terms=tuple(normalized.split()), mode="exact")
        providers = [
            p
            for p in self.search_registry.providers()
            if await self._allowed(principal, p.required_permission)
        ]

        async def one(provider: Any) -> Any:
            return await asyncio.wait_for(
                provider.search(query, principal, DEFAULT_CONTEXT, limit=5, cursor=None), PORT_TIMEOUT
            )

        results = await asyncio.gather(*(one(p) for p in providers), return_exceptions=True)
        items: list[dict[str, Any]] = []
        sources: list[SourceRef] = []
        failed = 0
        for result in results:
            if isinstance(result, BaseException) or result.state != "ok":
                failed += 1
            if isinstance(result, BaseException):
                continue
            for item in list(result.items)[:5]:
                snippet = "".join(s.text for s in item.snippet)[:300]
                items.append(
                    {"kind": item.kind, "title": item.title, "snippet": snippet, "route": item.url_ref}
                )
                sources.append(
                    SourceRef(
                        item.kind,
                        f"{item.kind}:{item.id}",
                        item.title,
                        "real",
                        utc_now(self.clock),
                        item.url_ref,
                    )
                )
        state: ResultState = (
            "ok" if not failed else ("partial" if items or failed < len(providers) else "unavailable")
        )
        return ToolResult(state, {"results": items[:20]}, sources[:20])

    # --- 011 wiki knowledge and contextual help --------------------------------------------------------
    async def wiki(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        port = self._port(KNOWLEDGE)
        if port is None:
            return ToolResult("unavailable", detail="knowledge base unavailable")
        hits = await asyncio.wait_for(
            port.search(str(params["query"]), principal, limit=5, for_ai=True), PORT_TIMEOUT
        )
        return ToolResult(
            "ok",
            {"pages": [{"title": h.title, "excerpt": h.excerpt[:800], "route": h.url} for h in hits]},
            [SourceRef("wiki", h.ref, h.title, "knowledge", None, h.url) for h in hits],
        )

    async def help(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        port = self._port(HELP)
        if port is None:
            return ToolResult("unavailable", detail="help unavailable")
        hits = await asyncio.wait_for(port.for_context(str(params["page"]), principal), PORT_TIMEOUT)
        return ToolResult(
            "ok",
            {"pages": [{"title": h.title, "excerpt": h.excerpt[:800], "route": h.url} for h in hits]},
            [SourceRef("wiki", h.ref, h.title, "knowledge", None, h.url) for h in hits],
        )

    # --- 006 service state -----------------------------------------------------------------------------
    async def services(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        states, directory = self._port(SERVICE_STATE), self._port(SERVICE_DIRECTORY)
        if states is None:
            return ToolResult("unavailable", detail="service status unavailable")
        names: dict[str, str] = {}
        if directory is not None:
            try:
                names = {s.id: s.name for s in await asyncio.wait_for(directory.services(), PORT_TIMEOUT)}
            except Exception:
                names = {}
        views = await asyncio.wait_for(states.all(), PORT_TIMEOUT)
        wanted = str(params.get("service") or "").casefold()
        rows = []
        sources = []
        for view in views:
            name = names.get(view.service_id, view.service_id)
            if wanted and wanted not in name.casefold() and wanted != view.service_id:
                continue
            # issue 171: what an answer needs — a small model lost itself in raw timestamps
            row: dict[str, Any] = {"service": name, "state": view.state}
            if view.availability is not None:  # a share of OK probes over 24 h
                row["availability_24h_percent"] = round(view.availability * 100, 1)
            if view.state not in OPERATIONAL:
                row["since"] = view.since.date().isoformat()
            rows.append(row)
            sources.append(
                SourceRef(
                    "service",
                    f"service:{view.service_id}",
                    name,
                    "real",
                    view.as_of,
                    f"/services/{view.service_id}",
                )
            )
        trouble = [r["service"] for r in rows if r["state"] not in OPERATIONAL]
        summary = {
            "all_operational": not trouble,
            "operational": len(rows) - len(trouble),
            "in_trouble": trouble,
        }
        return ToolResult("ok", {"summary": summary, "services": rows[:30]}, sources[:30])

    # --- 017 statistics --------------------------------------------------------------------------------
    async def statistics_list(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        port = self._port(STATISTICS)
        if port is None:
            return ToolResult("unavailable", detail="statistics unavailable")
        entries = await asyncio.wait_for(port.catalog(principal), PORT_TIMEOUT)
        return ToolResult(
            "ok",
            {
                "statistics": [
                    {"key": e.key, "domain": e.domain, "scope": e.scope} for e in entries if not e.locked
                ][:50]
            },
        )

    async def statistics_get(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        port = self._port(STATISTICS)
        if port is None:
            return ToolResult("unavailable", detail="statistics unavailable")
        days = int(params.get("days") or 30)
        result = await asyncio.wait_for(
            port.get(str(params["key"]), viewer=principal, period=Period("last_n_days", days=days)),
            PORT_TIMEOUT,
        )
        state: ResultState = _STAT_STATES.get(result.state, "unavailable")
        data: dict[str, Any] = {"key": result.key, "state": result.state, "value": result.value}
        if result.trend is not None:
            data["trend"] = {"direction": result.trend.direction, "percent": result.trend.percent}
        data["breakdown"] = list(result.breakdown)[:20]
        as_of: datetime | None = result.as_of
        sources = [
            SourceRef("statistic", f"statistic:{result.key}", result.key, "historical", as_of, "/statistics")
        ]
        return ToolResult(state, data, sources if state != "unavailable" else ())

    # --- 004 navigation --------------------------------------------------------------------------------
    async def navigate(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        """Only routes present in the user's own navigation view; others are omitted without a trace."""
        words = normalize_for_search(str(params["query"]), None).split()
        entries = [c for c in self.navigation.all() if c.kind == "entry" and c.route]
        allowed = await asyncio.gather(*(self._allowed(principal, c.required_permission) for c in entries))
        scored = []
        for entry, ok in zip(entries, allowed, strict=True):
            if not ok:
                continue
            haystack = normalize_for_search(
                " ".join((entry.key, entry.label_key, entry.route or "", *entry.keywords)), None
            )
            score = sum(1 for w in words if w in haystack)
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda pair: (-pair[0], pair[1].order_hint))
        suggestions = [{"route": e.route, "label_key": e.label_key, "key": e.key} for _, e in scored[:5]]
        return ToolResult(
            "ok",
            {"suggestions": suggestions},
            [
                SourceRef("page", f"page:{s['key']}", str(s["label_key"]), "real", None, s["route"])
                for s in suggestions
            ],
        )

    def tools(self) -> list[AITool]:
        def tool(
            name: str,
            description: str,
            permission: str,
            handler: Callable[[Principal, Mapping[str, Any]], Any],
            schema: Mapping[str, Any] = _QUERY,
        ) -> AITool:
            return AITool(name, description, schema, permission, "read", handler, owner=OWNER)

        return [
            tool(
                "search.query",
                "Search the portal (services, pages, tickets, media…) for the user.",
                "search.use",
                self.search,
            ),
            tool(
                "wiki.search", "Search wiki pages the assistant may use as knowledge.", "wiki.read", self.wiki
            ),
            tool(
                "help.page",
                "Help pages for the page the user is on (pass its route or help key).",
                "ai.use",
                self.help,
                {
                    "type": "object",
                    "properties": {"page": {"type": "string", "minLength": 1, "maxLength": 200}},
                    "required": ["page"],
                    "additionalProperties": False,
                },
            ),
            tool(
                "services.status",
                "Current state of connected services (optionally one service by name).",
                "services.read",
                self.services,
                {
                    "type": "object",
                    "properties": {"service": {"type": "string", "maxLength": 100}},
                    "additionalProperties": False,
                },
            ),
            tool(
                "statistics.list",
                "Statistics the user may view.",
                "statistics.read",
                self.statistics_list,
                {"type": "object", "properties": {}, "additionalProperties": False},
            ),
            tool(
                "statistics.get",
                "One statistic over the last N days (privacy rules apply).",
                "statistics.read",
                self.statistics_get,
                {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "minLength": 3, "maxLength": 96},
                        "days": {"type": "integer", "minimum": 1, "maximum": 365},
                    },
                    "required": ["key"],
                    "additionalProperties": False,
                },
            ),
            tool(
                "navigate.suggest",
                "Suggest portal pages the user can open for a need.",
                "ai.use",
                self.navigate,
            ),
        ]

    def register(self, registry: AIToolRegistry) -> None:
        for definition in self.tools():
            if registry.get(definition.name) is None:
                registry.register(definition)
