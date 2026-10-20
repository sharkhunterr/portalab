"""AI read tools (T031; for 018): catalog search, my history and recommendations. Each tool runs **as the
acting principal** (the user the assistant acts for), returns only what that user may see (never another
user's private history) and plain values only — no source URLs, tokens or service internals.

Issue 171: they are now offered to the assistant (they were written, never registered), with
``media.status``: where a title stands — found in the catalog, then its journey asked by the media page
(requested, approved, released, searched by the download manager, downloading, imported, available), each
step with the facts that explain it, and the step it is stuck at."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from portalab.capabilities.ai import AITool, AIToolRegistry, ResultState, SourceRef, ToolResult
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from portalab.core.time import Clock, utc_now
from portalab.modules.media.catalog import CatalogQuery
from portalab.modules.media.discovery.shelves import Discovery
from portalab.modules.media.permissions import MEDIA_READ
from portalab.modules.media.providers.ports import HistoryReader
from portalab.modules.media.sections.service import SEEN


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    permission: str
    parameters: Mapping[str, Any]
    run: Callable[[Principal, Mapping[str, Any]], Awaitable[Mapping[str, Any]]]


OWNER = "module:media"
STUCK = ("blocked", "failed")
UNDER_WAY = ("current", "waiting")
MAX_TEXT = 200


def _compact(value: Any, depth: int = 0) -> Any:
    """A journey's facts, small enough for the assistant's context: short texts, short lists."""
    if isinstance(value, str):
        return value[:MAX_TEXT]
    if isinstance(value, Mapping):
        return {str(k): _compact(v, depth + 1) for k, v in list(value.items())[:12]} if depth < 3 else None
    if isinstance(value, list | tuple):
        return [_compact(v, depth + 1) for v in value[:3]] if depth < 3 else None
    return value


class MediaAiTools:
    def __init__(
        self,
        catalog: CatalogQuery,
        history: HistoryReader,
        discovery: Discovery,
        journey: Any = None,
        clock: Clock | None = None,
        cleanup: Any = None,
        sections: Any = None,
    ) -> None:
        self.sections = sections  # issue 171: what the member saw of the title (the page's « viewing »)
        self.cleanup = cleanup  # issue 171: whether a title leaves the library (Maintainerr), and when
        self.catalog = catalog
        self.history = history
        self.discovery = discovery
        self.journey = journey
        self.clock = clock

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
                "What the current user recently watched, read, played or listened to, newest first "
                "(optionally only one kind: movie, episode, book, audiobook…).",
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
                {
                    "id": str(r.id),
                    "kind": r.kind,
                    "title": r.title,
                    "year": r.year,
                    "available": r.available,
                }
                for r, _ in rows
            ]
        }

    async def my_history(self, principal: Principal, params: Mapping[str, Any]) -> Mapping[str, Any]:
        user = principal.acting_for or principal.user_id
        if user is None or not await self._allowed(principal):
            return {"items": []}
        limit = int(params.get("limit") or 20)
        kind = str(params.get("kind") or "").strip() or None  # issue 171: « my last film » is a movie
        items = await self.history.for_user(user, principal, limit=min(max(1, limit), 50), kind=kind)
        return {
            "items": [
                {
                    "id": str(i.object_id),
                    "title": i.title,
                    "kind": i.kind,
                    "at": i.occurred_at.isoformat(),
                    "finished": i.completed,
                }
                for i in items
            ]
        }

    async def recommendations(self, principal: Principal, params: Mapping[str, Any]) -> Mapping[str, Any]:
        if not await self._allowed(principal):
            return {"items": []}
        rows, _ = await self.discovery.shelf("recommended", principal)
        return {"items": [{"id": str(r.id), "kind": r.kind, "title": r.title} for r in rows[:10]]}

    # --- issue 171: offered to the assistant --------------------------------------------------------------
    async def status(self, principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        title = str(params.get("title") or "").strip()[:200]
        wanted = str(params.get("id") or "").strip()
        if not title and not wanted:
            return ToolResult("error", {"error": "give the title or the id"})
        if not await self._allowed(principal):
            return ToolResult("ok", {"found": False, "title": title})
        found: list[Any] = []
        images: dict[Any, Any] = {}
        if wanted:  # the page the member is on names it (« media id=… »)
            try:
                view = await self.catalog.get(principal, UUID(wanted))
            except (ValueError, NotFound):
                return ToolResult("ok", {"found": False, "id": wanted})
            found, images = [view], {view.id: getattr(view, "image_id", None)}
        else:
            year = params.get("year")
            rows, _ = await self.catalog.browse(
                principal,
                q=title,
                kind=params.get("kind") or None,
                year=int(year) if isinstance(year, int) else None,
                limit=5,
            )
            found = [r for r, _ in rows]
            images = {r.id: image for r, image in rows}
        if not found:
            return ToolResult(
                "ok",
                {
                    "found": False,
                    "title": title,
                    "hint": "Not in the portal's catalog: nobody asked for it and it is not in the library. "
                    "It can be requested from the media page.",
                },
            )
        folded = (title or found[0].title).casefold()
        best = next((r for r in found if r.title.casefold() == folded), found[0])
        data: dict[str, Any] = {
            "found": True,
            "title": best.title,
            "year": best.year,
            "kind": best.kind,
            "available": bool(best.available),
            "other_matches": [f"{r.title} ({r.year})" if r.year else r.title for r in found if r is not best][
                :4
            ],
        }
        state: ResultState = "ok"
        if self.journey is not None:
            try:
                journey = await self.journey.journey(principal, best.id)
            except Exception:
                journey, state = None, "partial"  # a service away: what the catalog knows still answers
            if journey is not None:
                steps = [_compact(step) for step in journey.get("steps") or []]
                data["requested"] = journey.get("request") is not None
                data["request"] = _compact(journey.get("request"))
                data["download_manager"] = _compact(journey.get("manager"))
                data["steps"] = steps
                data["stuck_at"] = next((s["key"] for s in steps if s.get("status") in STUCK), None)
                data["under_way"] = next((s["key"] for s in steps if s.get("status") in UNDER_WAY), None)
                if not steps:
                    data["note"] = "Nobody asked for it and no download manager follows it."
        viewing = await self._viewing(principal, best.id, best.kind)
        if viewing:
            data["my_viewing"] = viewing
        leaving = await self._leaving(principal, best.id)
        if leaving:
            data["leaving_library"] = leaving
        return ToolResult(state, data, [self._card(best, images.get(best.id))])

    async def _viewing(self, principal: Principal, object_id: Any, kind: str) -> dict[str, Any] | None:
        """The member's own plays of the title (a series: its episodes), as the title's page shows them."""
        if self.sections is None:
            return None
        try:
            section = await self.sections.load("viewing", object_id, principal)
        except Exception:
            return None
        data = section.data or {}
        mine = [m for m in data.get("mine") or [] if isinstance(m, Mapping)]
        if not mine:
            return {"watched": False, "plays": 0}
        last = mine[0]
        out: dict[str, Any] = {
            "plays": int(data.get("mine_total") or len(mine)),
            "last_at": str(last.get("at"))[:10],
        }
        if kind in ("series", "season"):
            finished = {m.get("title") for m in mine if (m.get("progress") or 0) >= SEEN}
            out["episodes_finished"] = len(finished)
            out["last_episode"] = last.get("title")
            out["note"] = (
                "Counts only the episodes played lately (at most 30 plays): not a full season tally."
            )
        else:
            out["status"] = data.get("status") or "started"
            if data.get("percent") is not None:
                out["percent"] = round(float(data["percent"]) * 100)
        return out

    async def _leaving(self, principal: Principal, object_id: Any) -> dict[str, Any] | None:
        """« Leaving soon »: the cleanup rule that put it on the deletion list, the day it goes, and
        whether someone saved it (a member can spend a rescue on the title's page)."""
        user = principal.acting_for or principal.user_id
        if self.cleanup is None or user is None or not self.cleanup.configured():
            return None
        try:
            status = await self.cleanup.status(object_id, user)
        except Exception:
            return None
        if not status.get("leaving"):
            return None
        return {
            "deletion_list": True,
            "rules": sorted({str(e.get("collection") or "") for e in status["leaving"]} - {""})[:4],
            "delete_at": status.get("delete_at"),
            "saved": bool(status.get("saved")),
            "can_be_rescued": not status.get("saved"),
        }

    async def _posters(self, ids: list[str]) -> dict[str, str]:
        """The posters of some titles, as the portal's own image addresses (the cards beside an answer)."""
        try:
            async with self.catalog.database.session() as session:
                found = await CatalogQuery._images(session, [UUID(i) for i in ids])
        except Exception:
            return {}
        return {str(k): f"/api/v1/media/images/{v}" for k, v in found.items()}

    def _card(self, item: Any, image: Any) -> SourceRef:
        """Issue 171: a title as the answer's card — its poster and « year · kind » beside the answer."""
        return SourceRef(
            "media",
            f"media:{item.id}",
            item.title,
            "real",
            utc_now(self.clock),
            f"/media/{item.id}",
            image=f"/api/v1/media/images/{image}" if image else None,
            detail=" · ".join(str(v) for v in (item.year, item.kind) if v),
        )

    def assistant_tools(self) -> list[AITool]:
        """The tools above as the assistant's: the read ones answer in a ``ToolResult`` with their page."""

        def wrap(definition: ToolDefinition, schema: Mapping[str, Any]) -> AITool:
            async def handler(principal: Principal, params: Mapping[str, Any]) -> ToolResult:
                data = dict(await definition.run(principal, params))
                cards = [
                    SourceRef(
                        "media",
                        f"media:{i['id']}",
                        str(i.get("title") or ""),
                        "real",
                        utc_now(self.clock),
                        f"/media/{i['id']}",
                        detail=" · ".join(str(v) for v in (i.get("year"), i.get("kind")) if v),
                        image=i.get("image"),
                    )
                    for i in data.get("items", [])[:6]
                    if isinstance(i, Mapping) and i.get("id")
                ]
                # the posters are for the cards, not the model: its context stays small
                data["items"] = [
                    {k: v for k, v in i.items() if k != "image"} if isinstance(i, Mapping) else i
                    for i in data.get("items", [])
                ]
                return ToolResult("ok", data, cards)

            return AITool(
                definition.name,
                definition.description,
                schema,
                definition.permission,
                "read",
                handler,
                owner=OWNER,
            )

        search, history, recommended = self.definitions()
        return [
            wrap(
                search,
                {
                    "type": "object",
                    "properties": {
                        "q": {"type": "string", "minLength": 1, "maxLength": 200},
                        "kind": {
                            "type": "string",
                            "enum": ["movie", "series", "book", "audiobook", "game", "music"],
                        },
                        "genre": {"type": "string", "maxLength": 60},
                        "year": {"type": "integer", "minimum": 1870, "maximum": 2100},
                    },
                    "required": ["q"],
                    "additionalProperties": False,
                },
            ),
            wrap(
                history,
                {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                        "kind": {
                            "type": "string",
                            "enum": ["movie", "episode", "series", "book", "audiobook", "game", "music"],
                        },
                    },
                    "additionalProperties": False,
                },
            ),
            wrap(recommended, {"type": "object", "properties": {}, "additionalProperties": False}),
            AITool(
                "media.status",
                "Where a film, series, book or game stands for the portal: in the library or not, and if "
                "it was requested, each step of its journey (requested, approved, released, searched by the "
                "download manager, downloading, imported, available) with what explains it, and whether "
                "it is on the library's deletion list (« leaving soon »: the rule, the day) — use it to say "
                "why a title is not available yet or why it will leave. Give its title, or its id when the "
                "user is on its page.",
                {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "minLength": 1, "maxLength": 200},
                        "id": {"type": "string", "format": "uuid", "description": "the media id of the page"},
                        "kind": {"type": "string", "enum": ["movie", "series", "book", "audiobook", "game"]},
                        "year": {"type": "integer", "minimum": 1870, "maximum": 2100},
                    },
                    "additionalProperties": False,
                },
                MEDIA_READ,
                "read",
                self.status,
                owner=OWNER,
            ),
        ]

    def register(self, registry: AIToolRegistry) -> None:
        for tool in self.assistant_tools():
            if registry.get(tool.name) is None:
                registry.register(tool)
