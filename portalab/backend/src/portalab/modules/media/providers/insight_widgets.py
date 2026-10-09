"""027 dashboard widgets: media statistics, recently added, recently requested, upcoming releases and the
server's top of the week — posters when the catalog has them. Server-wide data is anonymous (titles and
counts, never who watched or asked)."""

import asyncio
from collections.abc import Coroutine, Iterable, Mapping
from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

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
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.common import strong_ids
from portalab.modules.media.insights.enrich import MetadataEnricher
from portalab.modules.media.insights.stats import CATEGORIES, InsightsQuery
from portalab.modules.media.insights.upcoming import Upcoming
from portalab.modules.media.models import (
    Activity,
    Image,
    MediaObject,
    MediaRequest,
    ObjectMetadata,
    PlaybackSession,
    SourceItem,
)
from portalab.modules.media.permissions import MEDIA_READ, MEDIA_REQUEST
from portalab.modules.media.requests.insights import GROUPS, RequestInsights, ids_of, kind_of, lookup_of

OWNER = "module:media"
CHARTS = ("bars", "area", "donut", "top", "figures")
PERIODS = ("7d", "30d", "90d", "365d", "all")
POSTERS = SizeLimits(default=Size(12, 3), min=Size(4, 1), max=Size(12, 6))


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
    size=SizeLimits(default=Size(6, 3), min=Size(3, 1), max=Size(12, 6)),
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
KIND_FILTER = {
    "type": "object",
    "properties": {"kind": {"type": "string", "enum": ["all", "movie", "series", "book"]}},
    "additionalProperties": False,
}
RECENTLY_ADDED = _definition(  # 027: what the services added last (their own date), newest first
    "media.recently_added",
    component="media.posters",
    icon="sparkles",
    events=("media.added",),
    schema=KIND_FILTER,
    defaults={"kind": "all"},
)
RECENT_RELEASES = _definition(  # 027: what came out last (release or air date) among what the library holds
    "media.recent_releases",
    component="media.posters",
    icon="clapperboard",
    events=("media.added",),
    schema=KIND_FILTER,
    defaults={"kind": "all"},
)
KINDS_OF = {"all": None, "movie": ("movie",), "series": ("series",), "book": ("book", "audiobook")}
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
    size=SizeLimits(default=Size(12, 4), min=Size(6, 1), max=Size(12, 8)),
    product="widget_poster_wall",
)
SHUFFLE = _definition(  # 027 (#12): a title drawn at random from the library, on a frieze of posters
    "media.shuffle",
    component="media.shuffle",
    icon="shuffle",
    size=SizeLimits(default=Size(12, 3), min=Size(4, 1), max=Size(12, 6)),
    schema=KIND_FILTER,
    defaults={"kind": "all"},
)
LIVING_WALL = _definition(  # 027 (#31): a wall of posters turning one by one (sold in the shop)
    "media.living_wall",
    component="media.living_wall",
    icon="apps",
    size=SizeLimits(default=Size(12, 4), min=Size(4, 1), max=Size(12, 8)),
    product="widget_living_wall",
)
SERVER_PLAYING = replace(  # 027 (#31): what plays on the server now — titles and progress, never who
    _definition(
        "media.server_playing",
        component="media.server_playing",
        icon="play",
        size=SizeLimits(default=Size(6, 3), min=Size(3, 1), max=Size(12, 6)),
        # 027: everyone's streams (nobody named) or only mine — it replaced « now playing »
        schema={
            "type": "object",
            "properties": {"scope": {"type": "string", "enum": ["all", "me"]}},
            "additionalProperties": False,
        },
        defaults={"scope": "all"},
    ),
    refresh=Refresh(mode="interval", interval_s=30),
    stale_after_s=120,
)
ON_THIS_DAY = _definition(  # 027 (#31): a year ago today — what I watched, what came into the library
    "media.on_this_day",
    component="media.on_this_day",
    icon="hourglass",
    size=SizeLimits(default=Size(6, 3), min=Size(3, 1), max=Size(12, 6)),
    product="widget_on_this_day",  # sold in the shop
)
NEXT_RELEASES = _definition(  # 027: what comes out next among what I asked for and the series I follow
    "media.next_releases",
    component="media.next_releases",
    icon="rocket",
    size=SizeLimits(default=Size(6, 3), min=Size(4, 1), max=Size(12, 6)),  # one row = compact
    product="widget_next_releases",  # sold in the shop
)
MY_SOON = _definition(
    "media.my_soon",
    component="media.soon",
    icon="clock",
    size=SizeLimits(default=Size(6, 3), min=Size(4, 1), max=Size(12, 6)),
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


async def details(database: Database, object_ids: Iterable[UUID]) -> dict[UUID, dict[str, Any]]:
    """027: what the cards of a title say of it — its year, genres, overview and rating (the metadata
    provider's, when it was enriched)."""
    wanted = set(object_ids)
    if not wanted:
        return {}
    async with database.session() as session:
        found = await session.execute(select(MediaObject).where(MediaObject.id.in_(wanted)))
        objects = found.scalars().all()
        rated = await session.execute(
            select(ObjectMetadata.object_id, ObjectMetadata.data["vote_average"].astext).where(
                ObjectMetadata.object_id.in_(wanted), ObjectMetadata.status == "found"
            )
        )
        ratings: dict[UUID, str | None] = {row[0]: row[1] for row in rated.all()}
    out: dict[UUID, dict[str, Any]] = {}
    for item in objects:
        rating = ratings.get(item.id)
        out[item.id] = {
            "year": item.year,
            "genres": [str(g) for g in (item.effective.get("genres") or [])][:3],
            "overview": str(item.effective.get("overview") or "")[:400] or None,
            "rating": round(float(rating), 1) if rating not in (None, "", "null") else None,
        }
    return out


async def with_posters(
    database: Database,
    enricher: MetadataEnricher | None,
    rows: list[dict[str, Any]],
    *,
    lookups: int = 40,
    detailed: bool = False,
) -> list[dict[str, Any]]:
    """Catalog posters for rows tied to an object; the metadata provider's poster (TMDB) for the others —
    at most ``lookups`` of them, a few at a time (cached by the enricher). ``detailed`` (027): each card
    also says its year, genres, overview and rating."""
    ids = [UUID(r["id"]) for r in rows if r.get("id")]
    images = await posters(database, ids)
    known = await details(database, ids) if detailed else {}
    gate = asyncio.Semaphore(6)

    async def fill(row: dict[str, Any], lookup: tuple[Any, ...], poster: bool) -> None:
        async with gate:
            if enricher is None:
                return
            brief = await enricher.brief(*lookup)
            if poster:
                row["poster_ref"] = brief.get("poster")
            if detailed:
                for field in ("overview", "genres", "rating"):
                    if not row.get(field) and brief.get(field):
                        row[field] = brief[field]
                if not row.get("year") and brief.get("release_date"):
                    row["year"] = int(str(brief["release_date"])[:4])

    pending: list[Coroutine[Any, Any, None]] = []
    for row in rows:
        object_id = UUID(row["id"]) if row.get("id") else None
        row["image_id"] = images.get(object_id) if object_id else None
        row["route"] = f"/media/{row['id']}" if row.get("id") else None
        if object_id in known:
            for field, value in known[object_id].items():
                if value and not row.get(field):
                    row[field] = value
        lookup = row.pop("_lookup", None)
        poster = row["image_id"] is None
        wanted = poster or (detailed and object_id not in known)
        if wanted and lookup and enricher is not None and len(pending) < lookups:
            pending.append(fill(row, lookup, poster))  # not in the library: what TMDB says of it
        elif poster:
            row["poster_ref"] = None
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

    async def cards(self, rows: list[dict[str, Any]], *, detailed: bool = False) -> list[dict[str, Any]]:
        return await with_posters(self.database, self.enricher, rows, detailed=detailed)


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
    """027: « Recently added » (``released=False``) or « Recent releases » — one card per work, newest first,
    with when it was added or released and the new episode of a series."""

    def __init__(self, database: Database, clock: Clock | None = None, *, released: bool = False) -> None:
        super().__init__(database, clock)
        self.released = released

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        from portalab.modules.media.discovery.recent import recent_releases, recently_added

        kinds = KINDS_OF.get(str(config.get("kind") or "all"))
        async with self.database.session() as session:
            recents = (
                await recent_releases(session, utc_now(self.clock).date(), limit=16, kinds=kinds)
                if self.released
                else await recently_added(session, limit=16, kinds=kinds)
            )
            rows = {
                row.id: row
                for row in (
                    await session.execute(
                        select(MediaObject).where(MediaObject.id.in_([r.object_id for r in recents]))
                    )
                ).scalars()
            }
        items = [
            {
                "id": str(r.object_id),
                "title": rows[r.object_id].title,
                "kind": rows[r.object_id].kind,
                "meta": r.episode or (str(rows[r.object_id].year) if rows[r.object_id].year else None),
                "at": r.at,
            }
            for r in recents
            if r.object_id in rows
        ]
        return self.payload(
            {
                "items": await self.cards(items, detailed=True),  # 027: the deck look tells about each one
                "mode": "released" if self.released else "added",
            }
        )


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
        return self.payload({"items": await self.cards(items, detailed=True)})


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


class NextReleasesWidget(_Base):
    """027: « next releases » — the coming releases (60 days) that concern the viewer: a title they asked for
    (its release, or the next episode of a series they requested) or a series they watched this past year
    (its next episode). One per title, the soonest first, each saying why it is there."""

    LIMIT = 8
    FOLLOWED = timedelta(days=365)

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
        me = principal.acting_for or principal.user_id
        if me is None:
            return self.payload({"items": []})
        now = utc_now(self.clock)
        async with self.database.session() as session:
            requests = (
                (await session.execute(select(MediaRequest).where(MediaRequest.requester_user_id == me)))
                .scalars()
                .all()
            )
            watched = (
                await session.execute(
                    select(Activity.work_id, Activity.parent_title)
                    .where(
                        Activity.user_id == me,
                        Activity.kind == "episode",
                        Activity.started_at >= now - self.FOLLOWED,
                    )
                    .distinct()
                )
            ).all()
        asked: set[tuple[str, str]] = set()
        for request in requests:
            asked |= ids_of(request)
        series = {str(work) for work, _ in watched if work}
        titles = {str(title).casefold() for _, title in watched if title}
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for release in await self.upcoming.list(60):
            if release["at"] <= now.isoformat():
                continue
            name = str(release["parent_title"] or release["title"])
            if name.casefold() in seen:
                continue
            if asked & set(strong_ids(release.get("ids") or {}).items()):
                reason = "requested"
            elif release["kind"] != "movie" and (release["object_id"] in series or name.casefold() in titles):
                reason = "watching"
            else:
                continue
            seen.add(name.casefold())
            items.append(
                {
                    "id": release["object_id"],
                    "title": name,
                    "subtitle": release["title"] if release["parent_title"] else None,
                    "kind": release["kind"],
                    "type": release["type"],
                    "season": release["season"],
                    "episode": release["episode"],
                    "at": release["at"],
                    "reason": reason,
                    "overview": release.get("overview"),
                    "_lookup": (
                        "movie" if release["kind"] == "movie" else "series",
                        dict(release.get("ids") or {}),
                        name,
                        None,
                    ),
                }
            )
            if len(items) >= self.LIMIT:
                break
        return self.payload({"items": await self.cards(items, detailed=True)})


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


class ShuffleWidget(_Base):
    """027 (#12): « shuffle » — titles drawn at random among what the library holds (films and series by
    default, or one kind), each with its poster, year, genres and overview. The block shows one and lets
    the member draw another; the others scroll behind it as a frieze."""

    DRAW = 24

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        kinds = KINDS_OF.get(str(config.get("kind") or "all")) or ("movie", "series")
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(MediaObject)
                        .where(
                            MediaObject.status == "active",
                            MediaObject.available.is_(True),
                            MediaObject.kind.in_(kinds),
                        )
                        .order_by(func.random())
                        .limit(self.DRAW * 3)  # some have no poster
                    )
                )
                .scalars()
                .all()
            )
        items = [
            {
                "id": str(row.id),
                "title": row.title,
                "kind": row.kind,
                "year": row.year,
                "genres": [str(g) for g in (row.effective.get("genres") or [])][:3],
                "overview": str(row.effective.get("overview") or "")[:400] or None,
            }
            for row in rows
        ]
        cards = [card for card in await self.cards(items) if card.get("image_id")][: self.DRAW]
        return self.payload({"items": cards})


class LivingWallWidget(ShuffleWidget):
    """027 (#31): the « living wall » — many posters at random from the library, which the block turns one
    by one to reveal others."""

    DRAW = 48


class ServerPlayingWidget(_Base):
    """027 (#31): « playing on the server » — the sessions running now (playing, paused, buffering), each
    with its title, poster and progress; the viewer's own are marked, the others name nobody."""

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        me = principal.acting_for or principal.user_id
        since = utc_now(self.clock) - timedelta(minutes=3)
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(PlaybackSession, MediaObject)
                    .outerjoin(MediaObject, MediaObject.id == PlaybackSession.object_id)
                    .where(
                        PlaybackSession.ended.is_(False),
                        PlaybackSession.state.in_(("playing", "paused", "buffering")),
                        PlaybackSession.updated_at >= since,
                        *([PlaybackSession.user_id == me] if config.get("scope") == "me" else []),
                    )
                    .order_by(PlaybackSession.started_at.desc())
                    .limit(12)
                )
            ).all()
            parents: dict[UUID, MediaObject] = {}
            pending = {o.parent_id for _, o in rows if o is not None and o.parent_id}
            for _ in range(2):  # an episode → its season → its series
                if not pending:
                    break
                found = (
                    (await session.execute(select(MediaObject).where(MediaObject.id.in_(pending))))
                    .scalars()
                    .all()
                )
                parents.update({o.id: o for o in found})
                pending = {o.parent_id for o in found if o.parent_id and o.parent_id not in parents}

        def series_of(item: MediaObject) -> MediaObject | None:
            parent = parents.get(item.parent_id) if item.parent_id else None
            if parent is not None and parent.kind == "season" and parent.parent_id:
                return parents.get(parent.parent_id, parent)
            return parent

        items = []
        for session_row, item in rows:
            series = series_of(item) if item is not None and item.kind == "episode" else None
            shown = series or item
            duration = session_row.duration_s or 0
            items.append(
                {
                    "id": str(shown.id) if shown is not None else None,
                    "title": shown.title if shown is not None else session_row.kind,
                    "subtitle": item.title if series is not None and item is not None else None,
                    "kind": session_row.kind,
                    "state": session_row.state,
                    "progress": min(1.0, session_row.position_s / duration) if duration else None,
                    # 027: how long is left (whole minutes), never who
                    "remaining_s": max(0, round(duration - session_row.position_s)) if duration else None,
                    "mine": session_row.user_id is not None and session_row.user_id == me,
                }
            )
        cards = await self.cards(items, detailed=True)
        mine = config.get("scope") == "me"
        return WidgetPayload(
            "available", as_of=utc_now(self.clock), data={"items": cards, "count": len(cards), "mine": mine}
        )


class OnThisDayWidget(_Base):
    """027 (#31): « a year ago » — around this date (± 5 days), each year back up to five: what I watched
    then (one card per title), and what came into the library (the services' own date). Every year that
    has something, the nearest first."""

    YEARS = 5
    AROUND = timedelta(days=5)
    ADDED = 12

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        me = principal.acting_for or principal.user_id
        today = utc_now(self.clock)
        moments = []
        for years in range(1, self.YEARS + 1):
            try:
                then = today.replace(year=today.year - years)
            except ValueError:  # the 29th of February
                then = today.replace(year=today.year - years, day=28)
            watched, added = await self._then(me, then)
            shown = {
                "watched": await self.cards(watched[:12]),
                "added": [c for c in await self.cards(added) if c.get("image_id")],  # with a poster
            }
            if shown["watched"] or shown["added"]:
                moments.append({"years": years, "date": then.date().isoformat(), **shown})
        return self.payload({"moments": moments} if moments else None)

    async def _then(self, me: UUID | None, then: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        start, end = then - self.AROUND, then + self.AROUND
        async with self.database.session() as session:
            plays = (
                (
                    await session.execute(
                        select(Activity)
                        .where(
                            Activity.user_id == me,
                            Activity.counted.is_(True),
                            Activity.kind != "live",
                            Activity.started_at.between(start, end),
                        )
                        .order_by(Activity.started_at)
                        .limit(80)
                    )
                )
                .scalars()
                .all()
                if me
                else []
            )
            # the services' own date of addition (what the library got then), one card per title
            arrivals = (
                await session.execute(
                    select(SourceItem.object_id, func.min(SourceItem.observed_at))
                    .join(MediaObject, MediaObject.id == SourceItem.object_id)
                    .where(
                        SourceItem.kind.in_(("movie", "series", "book", "audiobook")),
                        SourceItem.observed_at.between(start, end),
                        MediaObject.status == "active",
                    )
                    .group_by(SourceItem.object_id)
                    .order_by(func.min(SourceItem.observed_at))
                    .limit(self.ADDED)
                )
            ).all()
            objects = {
                o.id: o
                for o in (
                    await session.execute(
                        select(MediaObject).where(MediaObject.id.in_([r[0] for r in arrivals]))
                    )
                ).scalars()
            }
        seen: set[Any] = set()
        watched = []
        for row in plays:
            key = row.work_id or row.object_id or (row.parent_title or row.title)
            if key in seen:
                continue
            seen.add(key)
            series = row.kind == "episode" and row.parent_title
            work = row.work_id or row.object_id
            watched.append(
                {
                    "id": str(work) if work else None,
                    "title": row.parent_title if series else row.title,
                    "subtitle": row.title if series else None,
                    "kind": "series" if series else row.kind,
                    "at": row.started_at.isoformat(),
                }
            )
        added = [
            {"id": str(o.id), "title": o.title, "kind": o.kind, "year": o.year}
            for o in (objects.get(r[0]) for r in arrivals)
            if o is not None
        ]
        return watched, added


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


STATS = with_styles(STATS, "countup")  # 027 (#31)
RECENTLY_ADDED = with_styles(RECENTLY_ADDED, "deck")  # 027 (#31)
RECENT_RELEASES = with_styles(RECENT_RELEASES, "deck")  # 027 (#31)
RECENTLY_REQUESTED = with_styles(RECENTLY_REQUESTED, "deck")  # 027 (#31)
POSTER_WALL = with_styles(POSTER_WALL, "kenburns")  # 027 (#31)
