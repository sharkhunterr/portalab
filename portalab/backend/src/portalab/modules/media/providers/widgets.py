"""Dashboard widgets (T033; 009 SDK): ``media.continue``, ``media.recent``, ``media.now_playing`` and
``media.requests`` — the viewer's own data only, as declarative lists."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.media.discovery.shelves import Discovery
from portalab.modules.media.history.projection import HistoryProjection
from portalab.modules.media.permissions import MEDIA_READ, MEDIA_REQUEST
from portalab.modules.media.playback.poller import PlaybackPoller
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
        size=SizeLimits(default=Size(6, 3), min=Size(3, 2), max=Size(12, 6)),
        refresh=Refresh(mode="event", events=events) if events else Refresh(),
        stale_after_s=900,
        template="list",
    )


CONTINUE = _definition("media.continue", MEDIA_READ, ("media.playback_paused", "media.playback_finished"))
RECENT = _definition("media.recent", MEDIA_READ, ("media.added",))
NOW_PLAYING = _definition(
    "media.now_playing", MEDIA_READ, ("media.playback_started", "media.playback_finished")
)
REQUESTS = _definition("media.requests", MEDIA_REQUEST, ("media.request_updated", "media.request_available"))


class _Base:
    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock

    def payload(self, items: list[dict[str, Any]]) -> WidgetPayload:
        if not items:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        return WidgetPayload("available", as_of=utc_now(self.clock), data={"items": items})


class ContinueWidget(_Base):
    def __init__(self, history: HistoryProjection, clock: Clock | None = None) -> None:
        super().__init__(clock)
        self.history = history

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        rows = await self.history.continue_items(user, limit=8) if user else []
        images = await posters(self.history.database, (o.id for _, o in rows))
        return self.payload(
            [
                {
                    "title": o.title,
                    "route": f"/media/{o.id}",
                    "meta": f"{round(p.percent * 100)} %",
                    "progress": p.percent,  # 027: a bar under the title
                    "image_id": images.get(o.id),
                }
                for p, o in rows
            ]
        )


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


class NowPlayingWidget(_Base):
    def __init__(self, poller: PlaybackPoller, clock: Clock | None = None) -> None:
        super().__init__(clock)
        self.poller = poller

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        rows = await self.poller.now_playing(user) if user else []
        return self.payload(
            [
                {
                    "title": s.kind,
                    "route": f"/media/{s.object_id}" if s.object_id else "/media",
                    "meta": s.state,
                }
                for s in rows
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
