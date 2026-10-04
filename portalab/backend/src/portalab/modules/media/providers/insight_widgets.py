"""027 dashboard widgets: media statistics, recently added, recently requested, upcoming releases and the
server's top of the week — posters when the catalog has them. Server-wide data is anonymous (titles and
counts, never who watched or asked)."""

from collections.abc import Iterable, Mapping
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
from portalab.modules.media.permissions import MEDIA_READ

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
) -> WidgetDefinition:
    name = key.split(".", 1)[1]
    return WidgetDefinition(
        key=key,
        owner=OWNER,
        title_key=f"media:widget.{name}.title",
        description_key=f"media:widget.{name}.description",
        icon=icon,
        required_permission=MEDIA_READ,
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
        images = await posters(self.database, (UUID(r["id"]) if r.get("id") else None for r in rows))
        for row in rows:
            row["image_id"] = images.get(UUID(row["id"])) if row.get("id") else None
            row["route"] = f"/media/{row['id']}" if row.get("id") else None
            lookup = row.pop("_lookup", None)
            if row["image_id"] is None and lookup and self.enricher is not None:
                # not in the library: the metadata provider's poster (TMDB), served by the portal
                row["poster_ref"] = await self.enricher.poster(*lookup)
        return rows


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
    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(MediaRequest).order_by(MediaRequest.requested_at.desc()).limit(16)
                    )
                ).scalars()
            )
        items = [
            {
                "id": str(r.object_id) if r.object_id else None,
                "title": str(r.external_ref.get("title") or "?"),
                "kind": str(r.external_ref.get("kind") or ""),
                "state": r.state,
                "at": r.requested_at.isoformat(),
                "_lookup": (
                    "series" if r.external_ref.get("kind") in ("series", "tv") else "movie",
                    dict(r.external_ref.get("ids") or {}),
                    str(r.external_ref.get("title") or ""),
                    None,
                ),
            }
            for r in rows
        ]
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
