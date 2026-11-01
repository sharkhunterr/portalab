"""``media.digest`` provider (027): the library's news for the newsletters of the news desk — what came out
(release or air date), what arrived (the services' own dates) and what comes next (the release
calendars) — one entry per work, a new episode naming its series. #316: each with what its card tells
(picture, year, genres, overview, rating); and ``media.edition``: the period's figures, its most watched works
and the pictures an edition shows."""

from dataclasses import replace
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.media import DigestItem
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.discovery.recent import Recent, recent_releases, recently_added
from portalab.modules.media.images.service import ImageService
from portalab.modules.media.insights.stats import InsightsQuery
from portalab.modules.media.insights.upcoming import Upcoming
from portalab.modules.media.models import MediaObject
from portalab.modules.media.providers.insight_widgets import details, posters

PERIODS = ((7, "7d"), (30, "30d"), (90, "90d"), (365, "365d"))


async def described(database: Database, items: list[DigestItem]) -> list[DigestItem]:
    """#316: each title with its picture, year, genres, overview and rating."""
    ids = {UUID(i.object_id) for i in items if i.object_id}
    if not ids:
        return items
    pictures = await posters(database, ids)
    facts = await details(database, ids)
    out = []
    for item in items:
        if not item.object_id:
            out.append(item)
            continue
        key = UUID(item.object_id)
        fact = facts.get(key, {})
        out.append(
            replace(
                item,
                picture=pictures.get(key),
                year=item.year or fact.get("year"),
                genres=tuple(fact.get("genres") or ()),
                overview=fact.get("overview"),
                rating=fact.get("rating"),
            )
        )
    return out


class LibraryDigest:
    def __init__(self, database: Database, upcoming: Upcoming, clock: Clock | None = None) -> None:
        self.database = database
        self.upcoming_list = upcoming
        self.clock = clock

    async def _items(self, recents: list[Recent], keep: Any = None) -> list[DigestItem]:
        if not recents:
            return []
        async with self.database.session() as session:
            rows = {
                row.id: row
                for row in (
                    await session.execute(
                        select(MediaObject).where(MediaObject.id.in_([r.object_id for r in recents]))
                    )
                ).scalars()
            }
        out = []
        for recent in recents:
            row = rows.get(recent.object_id)
            if row is None or (keep is not None and not keep(recent)):
                continue
            out.append(
                DigestItem(
                    row.title,
                    row.kind,
                    recent.at[:10],
                    f"/media/{row.id}",
                    recent.episode,
                    object_id=str(row.id),
                    year=row.year,
                )
            )
        return await described(self.database, out)

    async def releases(self, since: date, until: date, limit: int) -> list[DigestItem]:
        async with self.database.session() as session:
            recents = await recent_releases(session, until, limit=limit * 3)
        return (await self._items(recents, lambda r: r.at[:10] >= since.isoformat()))[:limit]

    async def additions(self, since: datetime, limit: int) -> list[DigestItem]:
        async with self.database.session() as session:
            recents = await recently_added(session, limit=limit * 3)
        return (await self._items(recents, lambda r: r.at >= since.isoformat()))[:limit]

    async def upcoming(self, until: date, limit: int) -> list[DigestItem]:
        days = max(1, (until - utc_now(self.clock).date()).days)
        out: list[DigestItem] = []
        for release in await self.upcoming_list.list(min(days, 90)):
            at = str(release["at"])[:10]
            if at < utc_now(self.clock).date().isoformat() or at > until.isoformat():
                continue
            episode = (
                f"S{int(release.get('season') or 0):02d}E{int(release['episode']):02d}"
                if release.get("episode") is not None
                else None
            )
            object_id = release.get("object_id")
            out.append(
                DigestItem(
                    str(release.get("parent_title") or release.get("title") or ""),
                    "series" if release.get("kind") == "episode" else str(release.get("kind") or "movie"),
                    at,
                    f"/media/{object_id}" if object_id else "/media/insights",
                    episode or release.get("type"),
                    object_id=str(object_id) if object_id else None,
                )
            )
            if len(out) >= limit:
                break
        return await described(self.database, out)


class LibraryEdition:
    """``media.edition`` (#316): the period's figures for everyone (never who watched what), its most watched
    works as cards, and the pictures an edition shows."""

    def __init__(self, database: Database, insights: InsightsQuery, images: ImageService) -> None:
        self.database = database
        self.insights = insights
        self.images = images

    async def period(self, days: int, *, top: int) -> dict[str, Any]:
        key = next((name for length, name in PERIODS if days <= length), "365d")
        data = await self.insights.overview(period=key, category="all", user=None, manager=False, top=top)
        works = [w for w in data["top_works"] if w.get("id")][:top]
        cards = await described(
            self.database,
            [
                DigestItem(
                    str(w["title"]),
                    str(w["kind"]),
                    str(w.get("last_at") or "")[:10],
                    f"/media/{w['id']}",
                    object_id=str(w["id"]),
                    year=w.get("year"),
                )
                for w in works
            ],
        )
        plays = {str(w["id"]): w for w in works}
        return {
            "totals": data["totals"],
            "previous": data["previous"],
            "by_kind": data["by_kind"],
            "top": [
                {
                    "item": card,
                    "plays": int(plays[card.object_id or ""]["plays"]),
                    "seconds": float(plays[card.object_id or ""]["seconds"]),
                }
                for card in cards
            ],
        }

    async def picture(self, image_id: str) -> bytes | None:
        try:
            _, data = await self.images.content(UUID(image_id))
        except Exception:
            return None  # gone, or never was
        return data
