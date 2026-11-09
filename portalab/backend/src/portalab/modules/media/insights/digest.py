"""``media.digest`` provider (027): the library's news for the newsletters of the news desk — what came out
(release or air date), what arrived (the services' own dates) and what comes next (the release
calendars) — one entry per work, a new episode naming its series. #316: each with what its card tells
(picture, year, genres, overview, rating); and ``media.edition``: the period's figures, its most watched works
and the pictures an edition shows."""

import asyncio
import base64
import binascii
import logging
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.media import BOOK_SERIES, BookDetails, DigestItem, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.databases import TIMEOUT
from portalab.modules.media.discovery.recent import Recent, recent_releases, recently_added
from portalab.modules.media.images.service import ImageService
from portalab.modules.media.insights.enrich import MetadataEnricher
from portalab.modules.media.insights.stats import InsightsQuery
from portalab.modules.media.insights.upcoming import Upcoming
from portalab.modules.media.models import MediaObject, MediaRequest
from portalab.modules.media.providers.insight_widgets import details, posters, with_posters
from portalab.modules.media.requests.insights import kind_of, lookup_of

log = logging.getLogger(__name__)

PERIODS = ((7, "7d"), (30, "30d"), (90, "90d"), (365, "365d"))


def _book_ref(address: object) -> tuple[str, str] | None:
    """A book's database and its ref there, from the portal address a request keeps (#378): its cover
    (``/api/v1/media/book-covers?service=…&ref=…``) or its sheet (``/media/book?service=…&ref=…``)."""
    query = parse_qs(urlsplit(str(address or "")).query)
    service, ref = (query.get("service") or [""])[0], (query.get("ref") or [""])[0]
    return (service, ref) if service and ref else None


def cover_picture(service: str, ref: str) -> str:
    """A book's cover as an edition's picture id: « b- » and its database and ref, fit for an address."""
    return "b-" + base64.urlsafe_b64encode(f"{service}|{ref}".encode()).decode().rstrip("=")


def _cover_of(image_id: str) -> tuple[str, str] | None:
    try:
        told = base64.urlsafe_b64decode(image_id[2:] + "=" * (-len(image_id[2:]) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError):
        return None
    service, _, ref = told.partition("|")
    return (service, ref) if service and ref else None


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

    def __init__(
        self,
        database: Database,
        insights: InsightsQuery,
        images: ImageService,
        enricher: MetadataEnricher | None = None,
        clock: Clock | None = None,
        capabilities: CapabilityRegistry | None = None,
    ) -> None:
        self.database = database
        self.insights = insights
        self.images = images
        self.enricher = enricher
        self.clock = clock
        self.capabilities = capabilities

    def _books(self, service: str) -> Any:
        if self.capabilities is None:
            return None
        return next(
            (
                r.provider
                for r in self.capabilities.system_providers(BOOK_SERIES)
                if r.instance_ref == service
            ),
            None,
        )

    async def _book(self, sheet: object) -> BookDetails | None:
        """#378: a requested book as its database (Hardcover) tells it — none when it cannot say in time."""
        found = _book_ref(sheet)
        provider = self._books(found[0]) if found else None
        if found is None or provider is None:
            return None
        try:
            book = unwrap(await asyncio.wait_for(provider.book(found[1]), timeout=TIMEOUT))
        except Exception as exc:
            log.info("edition book lookup failed: %s: %s", type(exc).__name__, exc)
            return None
        return book if isinstance(book, BookDetails) else None

    async def period(self, days: int, *, top: int, tz: str = "UTC") -> dict[str, Any]:
        key = next((name for length, name in PERIODS if days <= length), "365d")
        data = await self.insights.overview(
            period=key, category="all", user=None, manager=False, top=top, tz=tz
        )
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
        # #324: what the charts draw — the time watched per day (or week), per weekday and hour, the genres
        weekdays = [0.0] * 7
        hours = [0.0] * 24
        for cell in data.get("heatmap") or []:
            weekdays[(int(cell["weekday"]) - 1) % 7] += float(cell["seconds"])
            hours[int(cell["hour"]) % 24] += float(cell["seconds"])
        timeline = data.get("timeline") or {}
        return {
            "totals": data["totals"],
            "previous": data["previous"],
            "by_kind": data["by_kind"],
            "timeline": {
                "unit": timeline.get("unit", "day"),
                "points": [
                    {"date": p["date"], "seconds": float(sum((p.get("seconds") or {}).values()))}
                    for p in timeline.get("points") or []
                ],
            },
            "weekdays": weekdays,
            "hours": hours,
            "genres": [
                {"name": g["name"], "seconds": float(g["seconds"])} for g in (data.get("genres") or [])[:6]
            ],
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
        """A portal image by its id — #323: or, « t-<file> », a title's poster from the metadata provider (a
        request not in the library yet); « b-… » (#387), a requested book's cover from its database."""
        try:
            if image_id.startswith("t-"):
                if self.enricher is None:
                    return None
                return await self.enricher.image(f"/{image_id[2:]}", "w342")
            if image_id.startswith("b-"):
                cover = _cover_of(image_id)
                provider = self._books(cover[0]) if cover else None
                if cover is None or provider is None:
                    return None
                return bytes(unwrap(await provider.cover(cover[1], "w342")))
            _, data = await self.images.content(UUID(image_id))
        except Exception:
            return None  # gone, or never was
        return data

    async def requests(self, days: int, limit: int) -> list[DigestItem]:
        """#323: what members asked for over the period, the latest first — each with its poster (the
        library's, else the metadata provider's) and its state; a book not in the library yet, its cover and
        what its database (Hardcover) tells of it (#387)."""
        since = utc_now(self.clock) - timedelta(days=days)
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(MediaRequest)
                        .where(MediaRequest.requested_at >= since)
                        .order_by(MediaRequest.requested_at.desc())
                        .limit(limit)
                    )
                ).scalars()
            )
        cards = await with_posters(
            self.database,
            self.enricher,
            [
                {
                    "id": str(r.object_id) if r.object_id else None,
                    "title": str(r.external_ref.get("title") or "?"),
                    "kind": kind_of(r),
                    "state": r.state,
                    "at": r.requested_at.date().isoformat(),
                    "_lookup": lookup_of(r),
                    "_ref": r.external_ref or {},
                }
                for r in rows
            ],
            detailed=True,
        )
        refs = [card.pop("_ref") for card in cards]
        books = await asyncio.gather(
            *(
                self._book(ref.get("sheet")) if not card.get("id") else _none()
                for card, ref in zip(cards, refs, strict=True)
            )
        )
        out = []
        for card, ref, book in zip(cards, refs, books, strict=True):
            poster = card.get("poster_ref")
            cover = _book_ref(ref.get("cover"))
            picture = (
                card.get("image_id")
                or (f"t-{str(poster).lstrip('/')}" if poster and str(poster).startswith("/") else None)
                or (cover_picture(*cover) if cover else None)
            )
            if book is not None:
                card["year"] = card.get("year") or book.year
                card["genres"] = card.get("genres") or list(book.genres)
                card["overview"] = card.get("overview") or book.description
                card["rating"] = card.get("rating") or book.rating
            if not card.get("route") and str(ref.get("sheet") or "").startswith("/media/"):
                card["route"] = ref["sheet"]
            card["year"] = card.get("year") or ref.get("year")
            out.append(
                DigestItem(
                    str(card["title"]),
                    "series" if card["kind"] in ("tv", "series") else str(card["kind"]),
                    str(card["at"]),
                    card.get("route") or "/media/requests",
                    str(card["state"]),
                    object_id=card.get("id"),
                    picture=picture,
                    year=card.get("year"),
                    genres=tuple(str(g) for g in (card.get("genres") or [])[:3]),
                    overview=card.get("overview"),
                    rating=card.get("rating"),
                )
            )
        return out


async def _none() -> None:
    return None
