"""027 dashboard widgets: media statistics, recently added, recently requested, upcoming releases and the
server's top of the week — posters when the catalog has them. Server-wide data is anonymous (titles and
counts, never who watched or asked)."""

import asyncio
from collections.abc import Coroutine, Iterable, Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.insights.enrich import MetadataEnricher
from portalab.modules.media.insights.stats import CATEGORIES, InsightsQuery
from portalab.modules.media.insights.upcoming import Upcoming
from portalab.modules.media.models import Image, MediaObject, MediaRequest
from portalab.modules.media.permissions import MEDIA_READ, MEDIA_REQUEST
from portalab.modules.media.requests.insights import GROUPS, RequestInsights, kind_of, lookup_of

OWNER = "module:media"
CHARTS = ("bars", "area", "donut", "top", "figures")
PERIODS = ("7d", "30d", "90d", "365d", "all")
POSTERS = SizeLimits(default=Size(12, 3), min=Size(4, 2), max=Size(12, 6))


def _definition(
    key: str,
    *,
    component: str,
    icon: str,
    size: SizeLimits = POSTERS,
    events: tuple[str, ...] = (),
    schema: Mapping[str, Any] | None = None,
    defaults: Mapping[str, Any] | None = None,
    permission: str = MEDIA_READ,
    product: str | None = None,
) -> WidgetDefinition:
    name = key.split(".", 1)[1]
    return WidgetDefinition(
        key=key,
        owner=OWNER,
        title_key=f"media:widget.{name}.title",
        description_key=f"media:widget.{name}.description",
        icon=icon,
        required_permission=permission,
        product=product,
        size=size,
        multiple=bool(schema),
        refresh=Refresh(mode="event", events=events) if events else Refresh(mode="interval", interval_s=900),
        stale_after_s=1800,
        component_id=component,
        config_schema=schema or {"type": "object", "properties": {}},
        config_defaults=defaults or {},
    )


STATS = _definition(
    "media.stats",
    component="media.stats",
    icon="chart",
    size=SizeLimits(default=Size(6, 3), min=Size(3, 2), max=Size(12, 6)),
    schema={
        "type": "object",
        "properties": {
            "scope": {"type": "string", "enum": ["me", "all"]},
            "period": {"type": "string", "enum": ["7d", "30d", "90d", "365d", "all"]},
            "category": {
                "type": "string",
                "enum": ["all", "movies", "series", "live", "music", "books", "audiobooks"],
            },
            "metric": {"type": "string", "enum": ["time", "plays"]},
            "chart": {"type": "string", "enum": ["bars", "area", "donut", "top", "figures"]},
        },
        "additionalProperties": False,
    },
    defaults={"scope": "me", "period": "30d", "category": "all", "metric": "time", "chart": "bars"},
)
RECENTLY_ADDED = _definition(
    "media.recently_added", component="media.posters", icon="sparkles", events=("media.added",)
)
RECENTLY_REQUESTED = _definition(
    "media.recently_requested",
    component="media.posters",
    icon="inbox",
    events=("media.request_updated", "media.request_available"),
    schema={
        "type": "object",
        "properties": {
            "scope": {"type": "string", "enum": ["all", "me"]},
            "period": {"type": "string", "enum": ["7d", "30d", "90d", "all"]},
            "kind": {"type": "string", "enum": ["all", "movie", "series"]},
            "state": {"type": "string", "enum": ["all", "pending", "approved", "available", "declined"]},
        },
        "additionalProperties": False,
    },
    defaults={"scope": "all", "period": "30d", "kind": "all", "state": "all"},
)
POSTER_WALL = _definition(  # 027: a Marketplace widget — owners only (product « widget_poster_wall »)
    "media.poster_wall",
    component="media.wall",
    icon="image",
    size=SizeLimits(default=Size(12, 4), min=Size(6, 3), max=Size(12, 8)),
    product="widget_poster_wall",
)
MY_SOON = _definition(
    "media.my_soon",
    component="media.soon",
    icon="clock",
    size=SizeLimits(default=Size(6, 3), min=Size(4, 2), max=Size(12, 6)),
    events=("media.request_updated", "media.request_available"),
    schema={
        "type": "object",
        "properties": {"scope": {"type": "string", "enum": ["me", "all"]}},
        "additionalProperties": False,
    },
    defaults={"scope": "me"},
    permission=MEDIA_REQUEST,
)
UPCOMING = _definition("media.upcoming", component="media.posters", icon="calendar")
TOP = _definition("media.top", component="media.posters", icon="trophy")


async def posters(database: Database, object_ids: Iterable[UUID | None]) -> dict[UUID, str]:
    wanted = {i for i in object_ids if i is not None}
    if not wanted:
        return {}
    async with database.session() as session:
        rows = await session.execute(
            select(Image.object_id, Image.id).where(Image.object_id.in_(wanted), Image.role == "poster")
        )
        return {object_id: str(image_id) for object_id, image_id in rows.all()}


async def with_posters(
    database: Database, enricher: MetadataEnricher | None, rows: list[dict[str, Any]], *, lookups: int = 40
) -> list[dict[str, Any]]:
    """Catalog posters for rows tied to an object; the metadata provider's poster (TMDB) for the others —
    at most ``lookups`` of them, a few at a time (cached by the enricher)."""
    images = await posters(database, (UUID(r["id"]) if r.get("id") else None for r in rows))
    gate = asyncio.Semaphore(6)

    async def fill(row: dict[str, Any], lookup: tuple[Any, ...]) -> None:
        async with gate:
            row["poster_ref"] = await enricher.poster(*lookup) if enricher is not None else None

    pending: list[Coroutine[Any, Any, None]] = []
    for row in rows:
        row["image_id"] = images.get(UUID(row["id"])) if row.get("id") else None
        row["route"] = f"/media/{row['id']}" if row.get("id") else None
        lookup = row.pop("_lookup", None)
        if row["image_id"] is None and lookup and enricher is not None and len(pending) < lookups:
            pending.append(fill(row, lookup))  # not in the library: TMDB's poster, served by the portal
    await asyncio.gather(*pending)
    return rows


class _Base:
    def __init__(
        self, database: Database, clock: Clock | None = None, enricher: MetadataEnricher | None = None
    ) -> None:
        self.database = database
        self.clock = clock
        self.enricher = enricher

    def payload(self, data: Mapping[str, Any] | None) -> WidgetPayload:
        empty = not data or (isinstance(data.get("items"), list) and not data["items"])
        return WidgetPayload("no-data" if empty else "available", as_of=utc_now(self.clock), data=data)

    async def cards(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await with_posters(self.database, self.enricher, rows)


class StatsWidget(_Base):
    """027: configurable — whose (me / server), over which period and category, which metric (time spent or
    plays) and which chart (bars, area, donut by kind, top titles, figures only)."""

    def __init__(self, database: Database, insights: InsightsQuery, clock: Clock | None = None) -> None:
        super().__init__(database, clock)
        self.insights = insights

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        scope = "all" if config.get("scope") == "all" else "me"
        period = (
            config.get("period") if config.get("period") in ("7d", "30d", "90d", "365d", "all") else "30d"
        )
        category = config.get("category") if config.get("category") in CATEGORIES else "all"
        data = await self.insights.overview(
            period=str(period),
            category=str(category),
            user=user if scope == "me" else None,
            manager=False,
        )
        if not data["totals"]["plays"]:
            return self.payload(None)
        top = await self.cards(data["top_works"][:5])
        return self.payload(
            {
                "scope": data["scope"],
                "period": data["period"]["key"],
                "category": data["category"],
                "metric": "plays" if config.get("metric") == "plays" else "time",
                "chart": config.get("chart") if config.get("chart") in CHARTS else "bars",
                "totals": data["totals"],
                "previous": data["previous"],
                "by_kind": data["by_kind"],
                "unit": data["timeline"]["unit"],
                "timeline": [
                    {"date": p["date"], "seconds": sum(p["seconds"].values()), "plays": p["plays"]}
                    for p in data["timeline"]["points"]
                ],
                "top": top,
            }
        )


class RecentlyAddedWidget(_Base):
    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(MediaObject.id, MediaObject.title, MediaObject.kind, MediaObject.year)
                    .where(
                        MediaObject.status == "active",
                        MediaObject.available.is_(True),
                        MediaObject.kind.in_(("movie", "series", "book", "audiobook", "game", "album")),
                    )
                    .order_by(MediaObject.first_seen_at.desc())
                    .limit(16)
                )
            ).all()
        items = [{"id": str(i), "title": t, "kind": k, "meta": str(y) if y else None} for i, t, k, y in rows]
        return self.payload({"items": await self.cards(items)})


class RecentlyRequestedWidget(_Base):
    """027: configurable — everyone's or mine, over which period, films or series, which state."""

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        query = select(MediaRequest)
        if config.get("scope") == "me":
            query = query.where(MediaRequest.requester_user_id == user)
        days = {"7d": 7, "30d": 30, "90d": 90}.get(str(config.get("period", "30d")))
        if days:
            query = query.where(MediaRequest.requested_at >= utc_now(self.clock) - timedelta(days=days))
        kind = config.get("kind")
        if kind == "movie":
            query = query.where(MediaRequest.external_ref["kind"].astext == "movie")
        elif kind == "series":
            query = query.where(MediaRequest.external_ref["kind"].astext.in_(("series", "tv")))
        states = GROUPS.get(str(config.get("state", "all")))
        if states:
            query = query.where(MediaRequest.state.in_(states))
        async with self.database.session() as session:
            rows = list(
                (await session.execute(query.order_by(MediaRequest.requested_at.desc()).limit(16))).scalars()
            )
        items = [
            {
                "id": str(r.object_id) if r.object_id else None,
                "title": str(r.external_ref.get("title") or "?"),
                "kind": kind_of(r),
                "state": r.state,
                "at": r.requested_at.isoformat(),
                "_lookup": lookup_of(r),
            }
            for r in rows
        ]
        return self.payload({"items": await self.cards(items)})


class MySoonWidget(_Base):
    """027: my requests coming soon — being downloaded or imported (with progress), or with a release date."""

    def __init__(
        self,
        database: Database,
        requests: RequestInsights,
        clock: Clock | None = None,
        enricher: MetadataEnricher | None = None,
    ) -> None:
        super().__init__(database, clock, enricher)
        self.requests = requests

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        items = await self.requests.soon(None if config.get("scope") == "all" else user, limit=12)
        return self.payload({"items": await self.cards(items)})


class UpcomingWidget(_Base):
    def __init__(
        self,
        database: Database,
        upcoming: Upcoming,
        clock: Clock | None = None,
        enricher: MetadataEnricher | None = None,
    ) -> None:
        super().__init__(database, clock, enricher)
        self.upcoming = upcoming

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        releases = await self.upcoming.list(30)
        now = utc_now(self.clock) - timedelta(hours=12)
        items = [
            {
                "id": r["object_id"],
                "title": r["parent_title"] or r["title"],
                "subtitle": r["title"] if r["parent_title"] else None,
                "kind": r["kind"],
                "type": r["type"],
                "season": r["season"],
                "episode": r["episode"],
                "at": r["at"],
                "available": r["available"],
                "_lookup": (
                    "movie" if r["kind"] == "movie" else "series",
                    dict(r.get("ids") or {}),
                    r["parent_title"] or r["title"],
                    None,
                ),
            }
            for r in releases
            if r["at"] >= now.isoformat()
        ][:16]
        return self.payload({"items": await self.cards(items)})


class TopWidget(_Base):
    def __init__(self, database: Database, insights: InsightsQuery, clock: Clock | None = None) -> None:
        super().__init__(database, clock)
        self.insights = insights

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        data = await self.insights.overview(period="7d", category="all", user=None, manager=False)
        items = [
            {
                "id": w["id"],
                "title": w["title"],
                "kind": w["kind"],
                "plays": w["plays"],
                "seconds": w["seconds"],
            }
            for w in data["top_works"]
        ]
        return self.payload({"items": await self.cards(items)})


class PosterWallWidget(TopWidget):
    """The server's 24 most watched titles of the month as a poster mosaic (sold in the shop)."""

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        data = await self.insights.overview(period="30d", category="all", user=None, manager=False, top=24)
        items = [
            {"id": w["id"], "title": w["title"], "kind": w["kind"], "plays": w["plays"]}
            for w in data["top_works"]
        ]
        return self.payload({"items": await self.cards(items)})
