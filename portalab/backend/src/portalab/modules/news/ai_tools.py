"""The assistant's announcements tool (issue 171): ``news.latest`` — the published announcements the member
may read (its audience rules apply), newest first, optionally matching words; each with its page."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.ai import AITool, AIToolRegistry, SourceRef, ToolResult
from portalab.core.authz_port import Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.news.permissions import NEWS_READ

OWNER = "module:news"
MAX_ITEMS = 6


class NewsAiTools:
    def __init__(self, articles: Any, clock: Clock | None = None) -> None:
        self.articles = articles
        self.clock = clock

    async def latest(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        query = str(params.get("query") or "").strip()[:200] or None
        limit = min(max(1, int(params.get("limit") or 5)), MAX_ITEMS)
        rows, _ = await self.articles.listing(principal, q=query)
        rows = rows[:limit]
        now = utc_now(self.clock)
        return ToolResult(
            "ok",
            {
                "announcements": [
                    {
                        "title": row.title,
                        "summary": (row.summary or "")[:400],
                        "published_at": row.published_at.isoformat() if row.published_at else None,
                    }
                    for row in rows
                ]
            },
            [
                SourceRef("news", f"news:{row.id}", row.title, "real", now, f"/news/{row.slug}")
                for row in rows
            ],
        )

    def tools(self) -> list[AITool]:
        return [
            AITool(
                "news.latest",
                "The portal's latest published announcements (title, summary, date), newest first; "
                "optionally only those matching some words.",
                {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "maxLength": 200},
                        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_ITEMS},
                    },
                    "additionalProperties": False,
                },
                NEWS_READ,
                "read",
                self.latest,
                owner=OWNER,
            )
        ]

    def register(self, registry: AIToolRegistry) -> None:
        for tool in self.tools():
            if registry.get(tool.name) is None:
                registry.register(tool)
