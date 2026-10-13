"""Dashboard widgets (T033; 009 SDK): ``media.continue``, ``media.recent`` and
``media.requests`` — the viewer's own data only, as declarative lists."""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from portalab.capabilities.dashboard import (
    Refresh,
    Size,
    SizeLimits,
    WidgetDefinition,
    WidgetPayload,
    with_styles,
)
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.media.discovery.shelves import Discovery
from portalab.modules.media.history.projection import HistoryProjection
from portalab.modules.media.permissions import MEDIA_READ, MEDIA_REQUEST
from portalab.modules.media.providers.insight_widgets import posters
from portalab.modules.media.requests.service import Requests

OWNER = "module:media"


def _definition(key: str, permission: str, events: tuple[str, ...]) -> WidgetDefinition:
    name = key.split(".", 1)[1]
    return WidgetDefinition(
        key=key,
        owner=OWNER,
        title_key=f"media:widget.{name}.title",
        description_key=f"media:widget.{name}.description",
        icon="film",
        required_permission=permission,
        size=SizeLimits(default=Size(6, 3), min=Size(3, 1), max=Size(12, 6)),  # 027: one row = compact
        refresh=Refresh(mode="event", events=events) if events else Refresh(),
        stale_after_s=900,
        template="list",
    )


CONTINUE = with_styles(  # 027 (#31): « ambient » — the title's poster as a blurred light behind
    replace(
        _definition("media.continue", MEDIA_READ, ("media.playback_paused", "media.playback_finished")),
        component_id="media.continue",  # 027: posters with a progress bar
        refresh=Refresh(),
        # #92: a click opens the title's page (the default), or resumes a book or an audiobook right away
        config_schema={
            "type": "object",
            "properties": {"open": {"type": "string", "enum": ["page", "resume"]}},
            "additionalProperties": False,
        },
        config_defaults={"open": "page"},
    ),
    "ambient",
)
RECENT = _definition("media.recent", MEDIA_READ, ("media.added",))
REQUESTS = _definition("media.requests", MEDIA_REQUEST, ("media.request_updated", "media.request_available"))


class _Base:
    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock

    def payload(self, items: list[dict[str, Any]]) -> WidgetPayload:
        if not items:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        return WidgetPayload("available", as_of=utc_now(self.clock), data={"items": items})


class ContinueWidget(_Base):
    """What I am in the middle of: the portal's own playback progress and (027) the services' history —
    films and episodes from Plex/Tautulli, books and audiobooks from Grimmory — with posters."""

    def __init__(
        self, history: HistoryProjection, clock: Clock | None = None, enricher: Any = None, player: Any = None
    ) -> None:
        super().__init__(clock)
        self.history = history
        self.enricher = enricher
        self.player = player  # 027 (#23): the media servers' own « Continue watching »

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        from portalab.modules.media.insights.continuing import in_progress, resume_item
        from portalab.modules.media.providers.insight_widgets import with_posters

        user = principal.acting_for or principal.user_id
        if user is None:
            return self.payload([])
        live = await self.player.continuing(user, limit=12) if self.player is not None else None
        rows = await self.history.continue_items(user, limit=8)
        if live is not None and live.services:  # those servers speak for their titles: their word wins
            theirs = await self.player.objects_on(live.services, [o.id for _, o in rows])
            rows = [(p, o) for p, o in rows if o.id not in theirs]
        known_live = await with_posters(
            self.history.database,
            self.enricher,
            [resume_item(point, object_id) for point, object_id in (live.points if live else [])],
            lookups=12,
        )
        images = await posters(self.history.database, (o.id for _, o in rows))
        items = [
            {
                "title": o.title,
                "id": str(o.id),
                "kind": o.kind,  # #20, #21: an audiobook or a book resumes straight away from the card
                "route": f"/media/{o.id}",
                "meta": f"{round(p.percent * 100)} %",
                "progress": p.percent,  # 027: a bar under the title
                "image_id": images.get(o.id),
                "at": p.last_occurred_at.isoformat(),
            }
            for p, o in rows
        ]
        items = [{**row, "route": row.get("route") or "/media/insights"} for row in known_live] + [
            item for item in items if item["route"] not in {row.get("route") for row in known_live}
        ]
        known = {item["route"] for item in items}
        history = await with_posters(
            self.history.database,
            self.enricher,
            await in_progress(
                self.history.database,
                user,
                utc_now(self.clock),
                limit=12,
                skip_families=live.families if live is not None else frozenset(),
            ),
            lookups=12,
        )
        for row in history:
            if row.get("route") and row["route"] in known:
                continue
            items.append({**row, "route": row.get("route") or "/media/insights"})
        # #20, #21: the most recent first, whatever told it (a server, the portal's player, listening or
        # reading in the portal, the imported history) — a book read this morning is not pushed out by films
        items.sort(key=lambda item: str(item.get("at") or ""), reverse=True)
        return self.payload(items[:10])


class RecentWidget(_Base):
    def __init__(self, discovery: Discovery, clock: Clock | None = None) -> None:
        super().__init__(clock)
        self.discovery = discovery

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        rows, _ = await self.discovery.shelf("new", principal)
        images = await posters(self.discovery.database, (o.id for o in rows[:8]))
        return self.payload(
            [
                {
                    "title": o.title,
                    "route": f"/media/{o.id}",
                    "meta": str(o.year) if getattr(o, "year", None) else None,
                    "image_id": images.get(o.id),
                }
                for o in rows[:8]
            ]
        )


class RequestsWidget(_Base):
    def __init__(self, requests: Requests, clock: Clock | None = None) -> None:
        super().__init__(clock)
        self.requests = requests

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        rows = await self.requests.mine(user, limit=8) if user else []
        images = await posters(self.requests.database, (r.object_id for r in rows))
        return self.payload(
            [
                {
                    "title": str(r.external_ref.get("title", "")),
                    "route": f"/media/{r.object_id}" if r.object_id else "/media/requests",
                    "state": r.state,
                    "at": r.requested_at.isoformat(),
                    "image_id": images.get(r.object_id) if r.object_id else None,
                }
                for r in rows
            ]
        )
