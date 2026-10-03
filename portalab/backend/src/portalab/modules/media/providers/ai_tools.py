"""AI read tools (T031; for 018): catalog search, my history and recommendations. Each tool runs **as the
acting principal** (the user the assistant acts for), returns only what that user may see (never another
user's private history) and plain values only — no source URLs, tokens or service internals."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from portalab.core.authz_port import Principal
from portalab.modules.media.catalog import CatalogQuery
from portalab.modules.media.discovery.shelves import Discovery
from portalab.modules.media.permissions import MEDIA_READ
from portalab.modules.media.providers.ports import HistoryReader


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    permission: str
    parameters: Mapping[str, Any]
    run: Callable[[Principal, Mapping[str, Any]], Awaitable[Mapping[str, Any]]]


class MediaAiTools:
    def __init__(self, catalog: CatalogQuery, history: HistoryReader, discovery: Discovery) -> None:
        self.catalog = catalog
        self.history = history
        self.discovery = discovery

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                "media.search_catalog",
                "Search the media catalog by title, kind, genre or year.",
                MEDIA_READ,
                {"q": "string", "kind": "string?", "genre": "string?", "year": "integer?"},
                self.search_catalog,
            ),
            ToolDefinition(
                "media.my_history",
                "What the current user recently watched, read, played or listened to.",
                MEDIA_READ,
                {"limit": "integer?"},
                self.my_history,
            ),
            ToolDefinition(
                "media.recommendations",
                "Media recommended for the current user.",
                MEDIA_READ,
                {},
                self.recommendations,
            ),
        ]

    async def _allowed(self, principal: Principal) -> bool:
        return await self.catalog._can(principal, MEDIA_READ)

    async def search_catalog(self, principal: Principal, params: Mapping[str, Any]) -> Mapping[str, Any]:
        if not await self._allowed(principal):
            return {"items": []}
        year = params.get("year")
        rows, _ = await self.catalog.browse(
            principal,
            q=str(params.get("q") or "")[:200] or None,
            kind=params.get("kind") or None,
            genre=params.get("genre") or None,
            year=int(year) if isinstance(year, int | str) and str(year).isdigit() else None,
            limit=10,
        )
        return {
            "items": [
                {"id": str(r.id), "kind": r.kind, "title": r.title, "year": r.year, "available": r.available}
                for r, _ in rows
            ]
        }

    async def my_history(self, principal: Principal, params: Mapping[str, Any]) -> Mapping[str, Any]:
        user = principal.acting_for or principal.user_id
        if user is None or not await self._allowed(principal):
            return {"items": []}
        limit = int(params.get("limit") or 20)
        items = await self.history.for_user(user, principal, limit=min(max(1, limit), 50))
        return {
            "items": [
                {"title": i.title, "kind": i.kind, "at": i.occurred_at.isoformat(), "finished": i.completed}
                for i in items
            ]
        }

    async def recommendations(self, principal: Principal, params: Mapping[str, Any]) -> Mapping[str, Any]:
        if not await self._allowed(principal):
            return {"items": []}
        rows, _ = await self.discovery.shelf("recommended", principal)
        return {"items": [{"id": str(r.id), "kind": r.kind, "title": r.title} for r in rows[:10]]}
