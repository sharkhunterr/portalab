"""Metadata enrichment (027): films and series of the catalog are completed by the metadata provider (TMDB)
— backdrop, cast and crew, saga, budget, revenue, certification, keywords… — a small batch per run, the
watched ones first. Found details are refreshed after a month; misses are retried later (spaced out) in
case the provider learns about the title. Images are served by the portal (fetched once, then cached).
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.media import METADATA, PEOPLE, MetadataRecord, unwrap
from portalab.capabilities.record_sink import Report, ServiceRef, SinkResult
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.insights.progress import Progress
from portalab.modules.media.models import Activity, ExternalId, MediaObject, ObjectMetadata
from portalab.modules.media.observability import log, metrics

JOB = "media.metadata_enrich"
TASK = "metadata"
BATCH = 100
CONCURRENCY = 4
TIMEOUT = 20
REFRESH = timedelta(days=30)
RETRY = timedelta(days=3)
MAX_ATTEMPTS = 5
KINDS = ("movie", "series")
DRIVEN_LIMIT = 20_000  # « sync now »: titles looked up in one go


DATA_VERSION = 2  # 027: 2 = alternative backdrops and posters (the artwork one swipes through)


def record_data(record: MetadataRecord) -> dict[str, Any]:
    data = asdict(record)
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in data.items()} | {"_v": DATA_VERSION}


class MetadataEnricher:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        language: Callable[[], Awaitable[str]],
        *,
        blobs: BlobStore | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.language = language
        self.blobs = blobs
        self.clock = clock
        self._images: dict[tuple[str, str], str] = {}
        self._posters: dict[tuple[Any, ...], dict[str, Any]] = {}
        self.progress = Progress(database)

    def provider(self) -> tuple[str, Any] | None:
        try:
            registrations = self.capabilities.system_providers(METADATA)
        except Exception:
            return None
        return (registrations[0].instance_ref, registrations[0].provider) if registrations else None

    def _due(self, before: datetime | None) -> Any:
        """Titles to look up: never looked up, found a month ago, missed a few days ago — or, for a full
        resync, everything not looked up since ``before``."""
        now = utc_now(self.clock)
        meta = ObjectMetadata
        stale = (
            meta.fetched_at < before
            if before is not None
            else or_(
                and_(meta.status == "found", meta.fetched_at < now - REFRESH),
                # details found before the portal kept more of them are looked up again
                and_(
                    meta.status == "found",
                    func.coalesce(meta.data["_v"].as_integer(), 1) < DATA_VERSION,
                ),
                and_(meta.status != "found", meta.attempts < MAX_ATTEMPTS, meta.fetched_at < now - RETRY),
            )
        )
        return and_(
            MediaObject.kind.in_(KINDS),
            MediaObject.status == "active",
            or_(meta.object_id.is_(None), stale),
        )

    async def due(self, limit: int = BATCH, *, before: datetime | None = None) -> list[MediaObject]:
        played = exists().where(Activity.work_id == MediaObject.id)
        async with self.database.session() as session:
            query = (
                select(MediaObject)
                .outerjoin(ObjectMetadata, ObjectMetadata.object_id == MediaObject.id)
                .where(self._due(before))
                .order_by(played.desc(), MediaObject.first_seen_at.desc())
                .limit(limit)
            )
            return list((await session.execute(query)).scalars())

    async def drive(self, service: ServiceRef, kind: str, report: Report) -> SinkResult:
        """027: « sync now » (and the scheduled sync) of the metadata service, from the services page:
        every title due is looked up, with its progress; a resync looks the whole catalog up again."""
        found = self.provider()
        if found is None or found[0] != str(service.service_id):
            return SinkResult()
        provider_ref, provider = found
        language = await self.language()
        before = utc_now(self.clock) if kind in ("resync_partial", "resync_full") else None
        async with self.database.session() as session:
            total = int(
                await session.scalar(
                    select(func.count())
                    .select_from(MediaObject)
                    .outerjoin(ObjectMetadata, ObjectMetadata.object_id == MediaObject.id)
                    .where(self._due(before))
                )
                or 0
            )
        total = min(total, DRIVEN_LIMIT)
        statuses: dict[str, int] = {}
        done = 0
        await report(0, total)
        await self.progress.set(TASK, utc_now(self.clock), running=True, done=0, total=total)
        gate = asyncio.Semaphore(CONCURRENCY)

        async def one(obj: MediaObject) -> None:
            async with gate:
                status = await self.enrich(obj, provider_ref, provider, language)
                statuses[status] = statuses.get(status, 0) + 1

        try:
            while done < total:
                due = await self.due(min(BATCH, total - done), before=before)
                if not due:
                    break
                await asyncio.gather(*(one(obj) for obj in due))
                done += len(due)
                await report(done, total)
                await self.progress.set(TASK, utc_now(self.clock), running=True, done=done, total=total)
        finally:
            await self.progress.set(TASK, utc_now(self.clock), running=False)
        if done and statuses.get("error", 0) == done:
            raise LookupError("the metadata service answered none of the lookups")
        return SinkResult(
            modified=statuses.get("found", 0),
            ignored=statuses.get("missing", 0),
            errored=statuses.get("error", 0),
        )

    async def run(self) -> int:
        found = self.provider()
        if found is None:
            return 0
        provider_ref, provider = found
        language = await self.language()
        due = await self.due()
        if not due:
            return 0
        await self.progress.set(TASK, utc_now(self.clock), running=True, total=len(due))
        gate = asyncio.Semaphore(CONCURRENCY)

        async def one(obj: MediaObject) -> None:
            async with gate:
                await self.enrich(obj, provider_ref, provider, language)

        try:
            await asyncio.gather(*(one(obj) for obj in due))
        finally:
            await self.progress.set(TASK, utc_now(self.clock), running=False)
        return len(due)

    async def enrich(self, obj: MediaObject, provider_ref: str, provider: Any, language: str) -> str:
        async with self.database.session() as session:
            ids = {
                scheme: value
                for scheme, value in (
                    await session.execute(
                        select(ExternalId.scheme, ExternalId.value).where(ExternalId.object_id == obj.id)
                    )
                ).all()
            }
        status, data = "missing", {}
        try:
            record = unwrap(
                await asyncio.wait_for(
                    provider.lookup(obj.kind, ids, obj.title, obj.year, language), timeout=TIMEOUT
                )
            )
            if record is not None:
                status, data = "found", record_data(record)
        except Exception as exc:
            status = "error"
            log.info("metadata lookup failed for %s: %s", obj.id, type(exc).__name__)
        metrics.increment(f"media.metadata.{status}")
        await self.save(obj.id, provider_ref, status, language, data)
        return status

    async def save(
        self, object_id: UUID, provider: str, status: str, language: str, data: dict[str, Any]
    ) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            statement = insert(ObjectMetadata).values(
                object_id=object_id,
                provider=provider[:64],
                status=status,
                language=language[:16],
                data=data,
                attempts=1,
                fetched_at=now,
            )
            await uow.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[ObjectMetadata.object_id],
                    set_={
                        "provider": statement.excluded.provider,
                        "status": statement.excluded.status,
                        "language": statement.excluded.language,
                        # a miss keeps the details found before
                        "data": data if status == "found" else ObjectMetadata.data,
                        "attempts": 1 if status == "found" else ObjectMetadata.attempts + 1,
                        "fetched_at": now,
                    },
                )
            )

    async def refresh(self, object_id: UUID) -> str | None:
        """Look one object up now (an administrator asked for it)."""
        found = self.provider()
        if found is None:
            return None
        async with self.database.session() as session:
            obj = await session.get(MediaObject, object_id)
        if obj is None or obj.kind not in KINDS:
            return None
        return await self.enrich(obj, found[0], found[1], await self.language())

    async def details(self, object_id: UUID) -> ObjectMetadata | None:
        async with self.database.session() as session:
            row = await session.get(ObjectMetadata, object_id)
        return row if row is not None and row.status == "found" else None

    async def brief(
        self, kind: str, ids: Mapping[str, str], title: str, year: int | None = None
    ) -> dict[str, Any]:
        """027: what the provider says of a title the library may not have (a request, an upcoming
        release) — its poster, release date, overview, genres and rating — looked up once, then
        remembered (misses too)."""
        found = self.provider()
        empty: dict[str, Any] = {"poster": None, "release_date": None}
        if found is None or kind not in KINDS or not title:
            return empty
        key = (kind, tuple(sorted(ids.items())), title.casefold(), year)
        if key in self._posters:
            return self._posters[key]
        brief = empty
        try:
            record = unwrap(
                await asyncio.wait_for(
                    found[1].lookup(kind, ids, title, year, await self.language()), timeout=TIMEOUT
                )
            )
            if record is not None:
                brief = {
                    "poster": record.poster,
                    "release_date": record.release_date,
                    "overview": record.overview,
                    "genres": list(record.genres)[:3],
                    "rating": record.vote_average,
                }
        except Exception:  # noqa: S110 — nothing known is fine
            pass
        if len(self._posters) > 5000:
            self._posters.clear()
        self._posters[key] = brief
        return brief

    async def poster(
        self, kind: str, ids: Mapping[str, str], title: str, year: int | None = None
    ) -> str | None:
        poster: str | None = (await self.brief(kind, ids, title, year))["poster"]
        return poster

    def _tmdb_images(self) -> tuple[str, Any] | None:
        """#92: without a metadata provider, TMDB's images through a service serving TMDB's people (Seerr)."""
        try:
            registrations = self.capabilities.system_providers(PEOPLE)
        except Exception:
            return None
        for registration in registrations:
            if (registration.metadata or {}).get("connector") in ("tmdb", "seerr"):
                return registration.instance_ref, registration.provider
        return None

    async def image(self, ref: str, size: str) -> bytes:
        """A provider image, fetched once then served from the blob store (or memory without one)."""
        found = self.provider() or self._tmdb_images()
        if found is None:
            raise LookupError("no metadata provider")
        key = (ref, size)
        if self.blobs is not None and key in self._images:
            try:
                return await self.blobs.get(self._images[key])
            except Exception:
                self._images.pop(key, None)
        fetch = getattr(found[1], "fetch_image", None) or found[1].portrait
        data: bytes = unwrap(await asyncio.wait_for(fetch(ref, size), timeout=TIMEOUT))
        if self.blobs is not None:
            stored = await self.blobs.put("media-metadata", data, content_type="image/jpeg")
            if len(self._images) > 5000:
                self._images.clear()
            self._images[key] = stored.key
        return data
