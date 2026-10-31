"""#299: the news sources the editors chose — each read on its own cadence (more slowly after failures), its
new items kept with a copied picture and the library titles and people they name, filtered by the source's
words, pruned after a while; and what « À la une », a title's page or « Mon fil » show of them."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.i18n import normalize_for_search
from portalab.capabilities.media import MENTIONS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.core.uploads import UnsafeUpload, reencode_image
from portalab.modules.news.models import Feed, FeedItem
from portalab.modules.news.sources.fetch import MAX_IMAGE, Fetched, FetchFailed, fetch
from portalab.modules.news.sources.parse import NotAFeed, ParsedFeed, ParsedItem, announced, parse

log = get_logger(__name__)
NAMESPACE = "news-feeds"
ALLOW_PRIVATE = "news.feeds.allowPrivateHosts"
RETENTION = "news.feeds.retentionDays"
PER_SOURCE = 200  # items kept per source at most
IMAGES = 15  # new pictures copied per reading
DUE_PER_SWEEP = 20
MAX_BACKOFF = timedelta(hours=24)


class SourceRefused(ValueError):
    """An address that is not a feed, or that cannot be read."""


@dataclass(frozen=True, slots=True)
class Preview:
    url: str  # the feed itself (a page announcing one: that one)
    feed: ParsedFeed
    mentions: list[list[dict[str, str]]]


def _words(values: Sequence[str]) -> list[str]:
    return [w for w in (normalize_for_search(v).strip() for v in values) if w][:30]


def _kept(item: ParsedItem, include: Sequence[str], exclude: Sequence[str]) -> bool:
    text = normalize_for_search(f"{item.title} {item.summary}")
    if include and not any(word in text for word in include):
        return False
    return not any(word in text for word in exclude)


class FeedSources:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        blobs: BlobStore | None,
        *,
        clock: Clock | None = None,
        transport: Any = None,
        resolver: Any = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.blobs = blobs
        self.clock = clock
        self.transport = transport  # tests: a fake network
        self.resolver = resolver

    async def _setting(self, key: str, default: Any) -> Any:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                value = (await providers[0].provider.get(key)).value
                return default if value is None else value
        except Exception:
            log.info("a news source setting was not read", extra={"fields": {"key": key}})
        return default

    async def _fetch(self, url: str, **kwargs: Any) -> Fetched:
        extra = {"resolver": self.resolver} if self.resolver is not None else {}
        allow = bool(await self._setting(ALLOW_PRIVATE, False))
        return await fetch(url, allow_private=allow, transport=self.transport, **extra, **kwargs)

    async def _mentions(self, items: Sequence[ParsedItem]) -> list[list[dict[str, str]]]:
        try:
            providers = self.capabilities.system_providers(MENTIONS)
            if not providers or not items:
                return [[] for _ in items]
            found = await providers[0].provider.mentions([f"{i.title}. {i.summary}" for i in items])
        except Exception:
            log.warning("news items not linked to the library")
            return [[] for _ in items]
        return [
            [{"kind": m.kind, "ref": m.ref, "label": m.label, "route": m.route} for m in mentions]
            for mentions in found
        ]

    # --- reading a source ---------------------------------------------------------------------------
    async def read(
        self, url: str, etag: str | None = None, modified: str | None = None
    ) -> tuple[Fetched, ParsedFeed | None]:
        """The source at ``url`` (a page announcing a feed: that feed). ``None``: not changed since."""
        try:
            got = await self._fetch(url, etag=etag, modified=modified)
            if got.status == 304:
                return got, None
            if "html" in got.content_type:
                feed_url = announced(got.body, got.url)
                if feed_url is None:
                    raise SourceRefused("this page announces no feed")
                got = await self._fetch(feed_url)
            return got, parse(got.body, got.url)
        except (FetchFailed, NotAFeed) as exc:
            raise SourceRefused(str(exc)) from exc

    async def preview(self, url: str) -> Preview:
        got, feed = await self.read(url)
        assert feed is not None
        return Preview(got.url, feed, await self._mentions(feed.items[:10]))

    async def _picture(self, url: str | None) -> str | None:
        if not url or self.blobs is None:
            return None
        try:
            got = await self._fetch(url, max_bytes=MAX_IMAGE, accept="image/*")
            if not got.content_type.startswith("image/"):
                return None
            data, content_type = reencode_image(got.body, max_side=800)
            return (await self.blobs.put(NAMESPACE, data, content_type=content_type)).key
        except (FetchFailed, UnsafeUpload, OSError):
            return None

    async def refresh(self, feed_id: UUID) -> int:
        """Read a source now: its new items kept (how many), its health and next reading noted."""
        now = utc_now(self.clock)
        async with self.database.session() as session:
            source = await session.get(Feed, feed_id)
            if source is None:
                return 0
            url, etag, modified = source.url, source.etag, source.modified
            include, exclude = _words(source.include_words), _words(source.exclude_words)
            every = timedelta(minutes=max(15, source.refresh_minutes))
            failures = source.failures
        try:
            got, feed = await self.read(url, etag, modified)
        except SourceRefused as exc:
            delay = min(every * (2 ** min(failures, 6)), MAX_BACKOFF)
            async with self.database.unit_of_work() as uow:
                await uow.session.execute(
                    update(Feed)
                    .where(Feed.id == feed_id)
                    .values(
                        status="error",
                        last_error=str(exc)[:300],
                        failures=Feed.failures + 1,
                        last_run_at=now,
                        next_run_at=now + delay,
                    )
                )
            return 0
        added = 0
        if feed is not None:
            async with self.database.session() as session:
                known = set(
                    (
                        await session.execute(select(FeedItem.guid).where(FeedItem.feed_id == feed_id))
                    ).scalars()
                )
            fresh = [i for i in feed.items if i.guid not in known and _kept(i, include, exclude)]
            mentions = await self._mentions(fresh)
            gate = asyncio.Semaphore(4)

            async def picture(item: ParsedItem, index: int) -> str | None:
                if index >= IMAGES:
                    return None
                async with gate:
                    return await self._picture(item.image)

            pictures = await asyncio.gather(*(picture(item, n) for n, item in enumerate(fresh)))
            rows = [
                {
                    "feed_id": feed_id,
                    "guid": item.guid,
                    "link": item.link[:1000],
                    "title": item.title[:300],
                    "summary": item.summary[:600],
                    "image_key": key,
                    "published_at": min(item.published or now, now),
                    "fetched_at": now,
                    "mentions": found,
                    "pinned": False,
                    "hidden": False,
                }
                for item, key, found in zip(fresh, pictures, mentions, strict=True)
            ]
            if rows:
                async with self.database.unit_of_work() as uow:
                    result = await uow.session.execute(
                        insert(FeedItem).values(rows).on_conflict_do_nothing().returning(FeedItem.id)
                    )
                    added = len(result.all())
        async with self.database.unit_of_work() as uow:
            values: dict[str, Any] = {
                "status": "ok",
                "last_error": None,
                "failures": 0,
                "last_run_at": now,
                "next_run_at": now + every,
            }
            if feed is not None:
                values |= {
                    "etag": (got.etag or "")[:200] or None,
                    "modified": (got.modified or "")[:80] or None,
                }
                if got.url != url:
                    values["url"] = got.url[:1000]  # a page announcing a feed: the feed from now on
            await uow.session.execute(update(Feed).where(Feed.id == feed_id).values(**values))
        await self.prune(feed_id)
        return added

    async def prune(self, feed_id: UUID | None = None) -> None:
        """Items older than the retention (unless pinned), and a source's beyond its newest ``PER_SOURCE``;
        their pictures when no other item shows them."""
        days = int(await self._setting(RETENTION, 30))
        limit = utc_now(self.clock) - timedelta(days=max(1, days))
        async with self.database.unit_of_work() as uow:
            session = uow.session
            ranked = select(
                FeedItem.id,
                func.row_number()
                .over(partition_by=FeedItem.feed_id, order_by=FeedItem.published_at.desc())
                .label("rank"),
            )
            if feed_id is not None:
                ranked = ranked.where(FeedItem.feed_id == feed_id)
            ranked_q = ranked.subquery()
            stale = select(ranked_q.c.id).where(ranked_q.c.rank > PER_SOURCE)
            gone = (
                await session.execute(
                    delete(FeedItem)
                    .where(
                        FeedItem.pinned.is_(False),
                        or_(FeedItem.published_at < limit, FeedItem.id.in_(stale)),
                        *((FeedItem.feed_id == feed_id,) if feed_id is not None else ()),
                    )
                    .returning(FeedItem.image_key)
                )
            ).scalars()
            keys = {k for k in gone if k}
            if keys:
                still = set(
                    (
                        await session.execute(select(FeedItem.image_key).where(FeedItem.image_key.in_(keys)))
                    ).scalars()
                )
                keys -= still
        if self.blobs is not None:
            for key in keys:
                try:
                    await self.blobs.delete(key)
                except Exception:
                    log.info("a news picture was not deleted")

    async def run_due(self) -> int:
        """Every source due (the periodic sweep): read one after the other."""
        now = utc_now(self.clock)
        async with self.database.session() as session:
            due = list(
                (
                    await session.execute(
                        select(Feed.id)
                        .where(
                            Feed.enabled.is_(True), or_(Feed.next_run_at.is_(None), Feed.next_run_at <= now)
                        )
                        .order_by(Feed.next_run_at.nulls_first())
                        .limit(DUE_PER_SWEEP)
                    )
                ).scalars()
            )
        added = 0
        for feed_id in due:
            try:
                added += await self.refresh(feed_id)
            except Exception:
                log.warning("a news source failed unexpectedly", extra={"fields": {"feed": str(feed_id)}})
        return added

    # --- what is shown ------------------------------------------------------------------------------
    async def items(
        self,
        *,
        feeds: Sequence[UUID] = (),
        titles: Sequence[str] = (),
        people: Sequence[str] = (),
        hidden: bool = False,
        limit: int = 30,
    ) -> list[tuple[FeedItem, Feed]]:
        """The latest items (pinned first when nothing is asked for), of some sources, or naming some library
        titles or people (any of them)."""
        stmt = select(FeedItem, Feed).join(Feed, Feed.id == FeedItem.feed_id).where(Feed.enabled.is_(True))
        if not hidden:
            stmt = stmt.where(FeedItem.hidden.is_(False))
        if feeds:
            stmt = stmt.where(FeedItem.feed_id.in_(list(feeds)))
        named = [{"kind": "title", "ref": t} for t in titles] + [{"kind": "person", "ref": p} for p in people]
        if named:
            stmt = stmt.where(or_(*(FeedItem.mentions.contains([n]) for n in named)))
        order: list[Any] = [FeedItem.published_at.desc()]
        if not named and not feeds:
            order.insert(0, FeedItem.pinned.desc())
        async with self.database.session() as session:
            rows = (await session.execute(stmt.order_by(*order).limit(limit))).all()
        return [(item, feed) for item, feed in rows]

    async def picture(self, item_id: UUID) -> tuple[str, bytes] | None:
        async with self.database.session() as session:
            key = await session.scalar(select(FeedItem.image_key).where(FeedItem.id == item_id))
        if not key or self.blobs is None:
            return None
        return key, await self.blobs.get(key)

    async def mark(self, item_id: UUID, *, pinned: bool | None = None, hidden: bool | None = None) -> bool:
        values = {k: v for k, v in (("pinned", pinned), ("hidden", hidden)) if v is not None}
        if not values:
            return True
        async with self.database.unit_of_work() as uow:
            result = await uow.session.execute(
                update(FeedItem).where(FeedItem.id == item_id).values(**values).returning(FeedItem.id)
            )
            return result.first() is not None

    # --- the editors' list ---------------------------------------------------------------------------
    async def sources(self) -> list[tuple[Feed, int]]:
        """Every source, with how many items it holds."""
        counts = select(FeedItem.feed_id, func.count().label("n")).group_by(FeedItem.feed_id).subquery()
        async with self.database.session() as session:
            rows = await session.execute(
                select(Feed, func.coalesce(counts.c.n, 0))
                .outerjoin(counts, counts.c.feed_id == Feed.id)
                .order_by(Feed.name)
            )
            return [(feed, int(n)) for feed, n in rows.all()]

    async def save(self, feed_id: UUID | None, fields: dict[str, Any]) -> UUID:
        """Create a source (read at once), or change one (its address changed: read again from scratch)."""
        now = utc_now(self.clock)
        fields = {**fields, "updated_at": now}
        async with self.database.unit_of_work() as uow:
            session = uow.session
            clash = await session.scalar(
                select(Feed.id).where(Feed.url == fields["url"], *((Feed.id != feed_id,) if feed_id else ()))
            )
            if clash is not None:
                raise SourceRefused("this source is already there")
            if feed_id is None:
                row = Feed(**fields, created_at=now, next_run_at=now, status="never", failures=0)
                session.add(row)
                await session.flush()
                return row.id
            current = await session.get(Feed, feed_id)
            if current is None:
                raise SourceRefused("no such source")
            if current.url != fields["url"]:
                fields |= {"etag": None, "modified": None, "next_run_at": now}
            for key, value in fields.items():
                setattr(current, key, value)
            return feed_id

    async def remove(self, feed_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            keys = {
                k
                for k in (
                    await uow.session.execute(select(FeedItem.image_key).where(FeedItem.feed_id == feed_id))
                ).scalars()
                if k
            }
            await uow.session.execute(delete(Feed).where(Feed.id == feed_id))
            if keys:
                keys -= set(
                    (
                        await uow.session.execute(
                            select(FeedItem.image_key).where(FeedItem.image_key.in_(keys))
                        )
                    ).scalars()
                )
        if self.blobs is not None:
            for key in keys:
                try:
                    await self.blobs.delete(key)
                except Exception:
                    log.info("a news picture was not deleted")
