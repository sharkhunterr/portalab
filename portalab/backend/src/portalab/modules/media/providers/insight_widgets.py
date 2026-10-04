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
from portalab.modules.media.insights.stats import InsightsQuery
from portalab.modules.media.insights.upcoming import Upcoming
from portalab.modules.media.models import Image, MediaObject, MediaRequest
from portalab.modules.media.permissions import MEDIA_READ

OWNER = "module:media"
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
            "period": {"type": "string", "enum": ["7d", "30d", "365d"]},
        },
        "additionalProperties": False,
    },
    defaults={"scope": "me", "period": "30d"},
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
    def __init__(self, database: Database, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    def payload(self, data: Mapping[str, Any] | None) -> WidgetPayload:
        empty = not data or (isinstance(data.get("items"), list) and not data["items"])
        return WidgetPayload("no-data" if empty else "available", as_of=utc_now(self.clock), data=data)

    async def cards(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        images = await posters(self.database, (UUID(r["id"]) if r.get("id") else None for r in rows))
        for row in rows:
            row["image_id"] = images.get(UUID(row["id"])) if row.get("id") else None
            row["route"] = f"/media/{row['id']}" if row.get("id") else None
        return rows


class StatsWidget(_Base):
    def __init__(self, database: Database, insights: InsightsQuery, clock: Clock | None = None) -> None:
        super().__init__(database, clock)
        self.insights = insights

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        scope = config.get("scope", "me")
        period = config.get("period", "30d")
        data = await self.insights.overview(
            period=period if period in ("7d", "30d", "365d") else "30d",
            category="all",
            user=user if scope != "all" else None,
            manager=False,
        )
        if not data["totals"]["plays"]:
            return self.payload(None)
        top = await self.cards(data["top_works"][:4])
        return self.payload(
            {
                "scope": data["scope"],
                "period": data["period"]["key"],
                "totals": data["totals"],
                "previous": data["previous"],
                "by_kind": data["by_kind"],
                "timeline": [
                    {"date": p["date"], "seconds": sum(p["seconds"].values())}
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
            }
            for r in rows
        ]
        return self.payload({"items": await self.cards(items)})


class UpcomingWidget(_Base):
    def __init__(self, database: Database, upcoming: Upcoming, clock: Clock | None = None) -> None:
        super().__init__(database, clock)
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
