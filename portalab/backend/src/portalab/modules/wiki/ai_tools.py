"""The assistant's wiki tool (issue 171): ``wiki.page`` — one page the member may read, by its address or
its title, **only if its editors let the assistant read it** (``readable_by_ai``); its text in Markdown,
cut to what an answer needs. Finding pages stays ``wiki.search`` (the knowledge port)."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.capabilities.ai import AITool, AIToolRegistry, SourceRef, ToolResult
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from portalab.core.time import Clock, utc_now
from portalab.modules.wiki.models import Page
from portalab.modules.wiki.permissions import WIKI_READ

OWNER = "module:wiki"
MAX_BODY = 4000


class WikiAiTools:
    def __init__(self, pages: Any, clock: Clock | None = None) -> None:
        self.pages = pages
        self.clock = clock

    async def _find(self, key: str) -> Any:
        found = await self.pages.find(key)
        if found is not None:
            return found
        async with self.pages.database.session() as session:  # by its title, then
            return await session.scalar(
                select(Page.id).where(func.lower(Page.title) == key.casefold()).limit(1)
            )

    async def page(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        key = str(params.get("page") or "").strip().strip("/").removeprefix("wiki/")[:200]
        if not key:
            return ToolResult("error", {"error": "give the page's address or title"})
        page_id = await self._find(key)
        if page_id is None:
            return ToolResult("ok", {"found": False, "page": key})
        try:
            view = await self.pages.view(page_id, principal)
        except NotFound:
            return ToolResult("ok", {"found": False, "page": key})
        if not view.readable_by_ai:
            return ToolResult(
                "ok", {"found": True, "title": view.title, "readable": False, "url": f"/wiki/{view.slug}"}
            )
        body = view.body_md
        return ToolResult(
            "ok",
            {
                "found": True,
                "title": view.title,
                "text": body[:MAX_BODY],
                "cut": len(body) > MAX_BODY,
                "updated_at": view.updated_at.isoformat(),
            },
            [
                SourceRef(
                    "wiki",
                    f"wiki:{view.id}",
                    view.title,
                    "knowledge",
                    utc_now(self.clock),
                    f"/wiki/{view.slug}",
                )
            ],
        )

    def tools(self) -> list[AITool]:
        return [
            AITool(
                "wiki.page",
                "Read one wiki page by its address (slug) or exact title — after wiki.search found it.",
                {
                    "type": "object",
                    "properties": {"page": {"type": "string", "minLength": 1, "maxLength": 200}},
                    "required": ["page"],
                    "additionalProperties": False,
                },
                WIKI_READ,
                "read",
                self.page,
                owner=OWNER,
            )
        ]

    def register(self, registry: AIToolRegistry) -> None:
        for tool in self.tools():
            if registry.get(tool.name) is None:
                registry.register(tool)
