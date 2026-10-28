"""Issue 190: the taste's widgets — « for you » (what my taste recommends, each title with its reason) and
« like it or not » (a title at a time to judge: like, not for me, seen, later; swiped or with buttons)."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.dashboard import Size, SizeLimits, WidgetPayload
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.providers.insight_widgets import KIND_FILTER, _definition, details, posters
from portalab.modules.media.taste.service import Pick, TasteService

FOR_YOU = _definition(
    "media.for_you",
    component="media.for_you",
    icon="heart",
    schema=KIND_FILTER,
    defaults={"kind": "all"},
)
TASTE = _definition(
    "media.taste",
    component="media.taste",
    icon="thumbs-up",
    size=SizeLimits(default=Size(4, 4), min=Size(3, 3), max=Size(12, 6)),
)
KINDS = {"all": None, "movie": ("movie",), "series": ("series",), "book": ("book", "audiobook")}


async def cards(database: Database, picks: list[Pick]) -> list[dict[str, Any]]:
    ids = [p.work.id for p in picks]
    images = await posters(database, ids)
    facts = await details(database, ids)
    out = []
    for pick in picks:
        fact = facts.get(pick.work.id, {})
        out.append(
            {
                "id": str(pick.work.id),
                "title": pick.work.title,
                "kind": pick.work.kind,
                "year": pick.work.year or fact.get("year"),
                "genres": fact.get("genres") or [],
                "rating": fact.get("rating"),
                "author": fact.get("author"),
                "overview": str(fact.get("overview") or "")[:400] or None,
                "image_id": str(images[pick.work.id]) if pick.work.id in images else None,
                "route": f"/media/{pick.work.id}",
                "reason": pick.reason,
                "seen": pick.seen,
            }
        )
    return out


class _Taste:
    def __init__(self, database: Database, taste: TasteService, clock: Clock | None = None) -> None:
        self.database = database
        self.taste = taste
        self.clock = clock

    def payload(self, items: list[dict[str, Any]]) -> WidgetPayload:
        if not items:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        return WidgetPayload("available", as_of=utc_now(self.clock), data={"items": items})


class ForYouWidget(_Taste):
    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        if user is None:
            return self.payload([])
        kinds = KINDS.get(str(config.get("kind") or "all"))
        picks = await self.taste.recommend(user, limit=12, kinds=kinds)
        return self.payload(await cards(self.database, picks))


class TasteWidget(_Taste):
    """The first cards come with the block; the next ones are asked for as the member judges them."""

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        if user is None:
            return self.payload([])
        return self.payload(await cards(self.database, await self.taste.deck(user, limit=12)))
