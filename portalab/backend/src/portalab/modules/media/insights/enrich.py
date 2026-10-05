"""Metadata enrichment (027): films and series of the catalog are completed by the metadata provider (TMDB)
— backdrop, cast and crew, saga, budget, revenue, certification, keywords… — a small batch per run, the
watched ones first. Found details are refreshed after a month; misses are retried later (spaced out) in
case the provider learns about the title. Images are served by the portal (fetched once, then cached).
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.media import METADATA, MetadataRecord, unwrap
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


def record_data(record: MetadataRecord) -> dict[str, Any]:
    data = asdict(record)
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in data.items()}


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
        self._posters: dict[tuple[Any, ...], dict[str, str | None]] = {}
        self.progress = Progress(database)

    def provider(self) -> tuple[str, Any] | None:
        try:
            registrations = self.capabilities.system_providers(METADATA)
        except Exception:
            return None
        return (registrations[0].instance_ref, registrations[0].provider) if registrations else None

    async def due(self, limit: int = BATCH) -> list[MediaObject]:
        now = utc_now(self.clock)
        meta = ObjectMetadata
        played = exists().where(Activity.work_id == MediaObject.id)
        async with self.database.session() as session:
            query = (
                select(MediaObject)
                .outerjoin(meta, meta.object_id == MediaObject.id)
                .where(
                    MediaObject.kind.in_(KINDS),
                    MediaObject.status == "active",
                    or_(
                        meta.object_id.is_(None),
                        and_(meta.status == "found", meta.fetched_at < now - REFRESH),
                        and_(
                            meta.status != "found",
                            meta.attempts < MAX_ATTEMPTS,
                            meta.fetched_at < now - RETRY,
                        ),
                    ),
                )
                .order_by(played.desc(), MediaObject.first_seen_at.desc())
                .limit(limit)
            )
            return list((await session.execute(query)).scalars())

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
    ) -> dict[str, str | None]:
        """027: poster and release date of a title the library may not have (a request, an upcoming
        release) — looked up once at the provider, then remembered (misses too)."""
        found = self.provider()
        if found is None or kind not in KINDS or not title:
            return {"poster": None, "release_date": None}
        key = (kind, tuple(sorted(ids.items())), title.casefold(), year)
        if key in self._posters:
            return self._posters[key]
        brief: dict[str, str | None] = {"poster": None, "release_date": None}
        try:
            record = unwrap(
                await asyncio.wait_for(
                    found[1].lookup(kind, ids, title, year, await self.language()), timeout=TIMEOUT
                )
            )
            if record is not None:
                brief = {"poster": record.poster, "release_date": record.release_date}
        except Exception:  # noqa: S110 — nothing known is fine
            pass
        if len(self._posters) > 5000:
            self._posters.clear()
        self._posters[key] = brief
        return brief

    async def poster(
        self, kind: str, ids: Mapping[str, str], title: str, year: int | None = None
    ) -> str | None:
        return (await self.brief(kind, ids, title, year))["poster"]

    async def image(self, ref: str, size: str) -> bytes:
        """A provider image, fetched once then served from the blob store (or memory without one)."""
        found = self.provider()
        if found is None:
            raise LookupError("no metadata provider")
        key = (ref, size)
        if self.blobs is not None and key in self._images:
            try:
                return await self.blobs.get(self._images[key])
            except Exception:
                self._images.pop(key, None)
        data: bytes = unwrap(await asyncio.wait_for(found[1].fetch_image(ref, size), timeout=TIMEOUT))
        if self.blobs is not None:
            stored = await self.blobs.put("media-metadata", data, content_type="image/jpeg")
            if len(self._images) > 5000:
                self._images.clear()
            self._images[key] = stored.key
        return data
