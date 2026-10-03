"""``media.library`` ``RecordSink`` (T012; R4, 005 contract): idempotent upserts keyed by
``(service_id, external_id)``; a late (older) observation never overwrites a newer one; ``removed`` only
deactivates — objects, history and requests are never deleted by a sync; payloads are validated and
sanitized (unknown fields dropped, image URLs stripped of credentials/query strings). After each batch the
touched objects are resolved (identity), recomputed (fields) and their availability re-derived; changes
are published as ``media.*`` events (ids only)."""

from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.media import LIBRARY, LibraryPayload
from portalab.capabilities.media_core import MediaTypeRegistry
from portalab.capabilities.record_sink import ServiceRef, SinkResult
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.media.common import payload_hash, safe_ref
from portalab.modules.media.fields.resolver import FieldResolver
from portalab.modules.media.identity.resolver import IdentityResolver
from portalab.modules.media.models import FieldCandidate, Image, MediaObject, SourceItem
from portalab.modules.media.observability import log, metrics


class CatalogWriter:
    """Shared write side: identity, fields, availability and catalog events for a set of objects."""

    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        identity: IdentityResolver,
        fields: FieldResolver,
        *,
        clock: Clock | None = None,
        on_image: Callable[[AsyncSession, UUID], Awaitable[None]] | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.identity = identity
        self.fields = fields
        self.clock = clock
        self.on_image = on_image

    async def publish(self, session: AsyncSession, name: str, payload: dict[str, Any], dedup: str) -> None:
        await self.events.publish(
            session, name, payload, occurred_at=utc_now(self.clock), source="media", dedup_key=dedup
        )

    async def refresh(self, session: AsyncSession, object_id: UUID, *, created: bool = False) -> None:
        """Recompute fields and availability of one object and publish what changed."""
        row = await session.get(MediaObject, object_id)
        if row is None or row.status == "merged":
            return
        changed = await self.fields.recompute(session, object_id)
        counts = (
            await session.execute(
                select(
                    func.count().filter(SourceItem.active.is_(True), SourceItem.availability == "available")
                ).where(SourceItem.object_id == object_id)
            )
        ).one()
        available = int(counts[0])
        now = utc_now(self.clock)
        stamp = now.isoformat()
        payload = {"object": str(object_id), "kind": row.kind}
        if created:
            await self.publish(session, "media.added", payload, f"media.added:{object_id}")
        elif changed:
            await self.publish(session, "media.updated", payload, f"media.updated:{object_id}:{stamp}")
            row.updated_at = now
        if row.available != (available > 0):
            row.available = available > 0
            row.updated_at = now
            await self.publish(
                session,
                "media.availability_changed",
                {**payload, "available": row.available},
                f"media.availability:{object_id}:{stamp}",
            )
        if "image" in changed and self.on_image is not None:
            await self.on_image(session, object_id)


class LibrarySink:
    capability = LIBRARY

    def __init__(
        self, writer: CatalogWriter, types: MediaTypeRegistry, *, clock: Clock | None = None
    ) -> None:
        self.writer = writer
        self.types = types
        self.clock = clock

    @property
    def database(self) -> Database:
        return self.writer.database

    def _sanitize(self, record: SourceRecord) -> dict[str, Any] | None:
        try:
            payload = LibraryPayload.model_validate(dict(record.payload))
        except ValidationError:
            return None
        data = payload.model_dump(exclude_none=True)
        image = safe_ref(payload.image)
        if image:
            data["image"] = image
        else:
            data.pop("image", None)
        return data

    async def upsert(self, records: Sequence[SourceRecord], service: ServiceRef) -> SinkResult:
        added = modified = ignored = errored = 0
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            touched: dict[UUID, bool] = {}
            removed: dict[UUID, bool] = {}
            for record in records:
                if record.removed:
                    count = await self._deactivate(session, [record.external_id], service, removed)
                    modified += count
                    ignored += 0 if count else 1
                    continue
                data = self._sanitize(record) if self.types.get(record.kind) is not None else None
                if data is None:
                    errored += 1
                    metrics.increment("media.sink.rejected")
                    continue
                digest = payload_hash(data)
                item = (
                    await session.execute(
                        select(SourceItem)
                        .where(
                            SourceItem.service_id == service.service_id,
                            SourceItem.external_id == record.external_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                availability = "available" if data.get("available", True) else "unavailable"
                if item is not None and item.observed_at > record.observed_at:
                    ignored += 1  # late record: an older observation never overwrites a newer one
                    continue
                if item is not None and item.payload_hash == digest and item.active:
                    item.last_seen_at = now
                    ignored += 1
                    continue
                if item is None:
                    item = SourceItem(
                        service_id=service.service_id,
                        source_system=service.source_system,
                        capability=LIBRARY,
                        external_id=record.external_id,
                        kind=record.kind,
                        active=True,
                        availability=availability,
                        payload=data,
                        payload_hash=digest,
                        observed_at=record.observed_at,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                    session.add(item)
                    await session.flush()
                    added += 1
                else:
                    item.payload, item.payload_hash, item.kind = data, digest, record.kind
                    item.active, item.availability = True, availability
                    item.observed_at, item.last_seen_at = record.observed_at, now
                    modified += 1
                attached = await self.writer.identity.attach(session, item, now)
                await self.writer.fields.store_candidates(session, item)
                touched[attached.object_id] = touched.get(attached.object_id, False) or attached.created
            for object_id, created in touched.items():
                await self.writer.refresh(session, object_id, created=created)
            for object_id in removed:
                if object_id not in touched:
                    await self.writer.refresh(session, object_id)
                await self._removed(session, object_id)
        return SinkResult(added=added, modified=modified, ignored=ignored, errored=errored)

    async def _deactivate(
        self,
        session: AsyncSession,
        external_ids: Sequence[str],
        service: ServiceRef,
        touched: dict[UUID, bool],
    ) -> int:
        items = (
            (
                await session.execute(
                    select(SourceItem).where(
                        SourceItem.service_id == service.service_id,
                        SourceItem.external_id.in_(list(external_ids)),
                        SourceItem.active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        for item in items:
            item.active, item.availability = False, "unavailable"
            if item.object_id is not None:
                touched.setdefault(item.object_id, False)
        return len(items)

    async def deactivate(self, external_ids: Sequence[str], service: ServiceRef) -> int:
        async with self.database.unit_of_work() as uow:
            touched: dict[UUID, bool] = {}
            count = await self._deactivate(uow.session, external_ids, service, touched)
            for object_id in touched:
                await self.writer.refresh(uow.session, object_id)
                await self._removed(uow.session, object_id)
        return count

    async def _removed(self, session: AsyncSession, object_id: UUID) -> None:
        active = await session.scalar(
            select(func.count()).where(SourceItem.object_id == object_id, SourceItem.active.is_(True))
        )
        row = await session.get(MediaObject, object_id)
        if not active and row is not None:
            await self.writer.publish(
                session,
                "media.removed",
                {"object": str(object_id), "kind": row.kind},
                f"media.removed:{object_id}:{utc_now(self.clock).isoformat()}",
            )

    async def active_ids(self, service: ServiceRef) -> set[str]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(SourceItem.external_id).where(
                    SourceItem.service_id == service.service_id, SourceItem.active.is_(True)
                )
            )
            return {row[0] for row in rows}

    async def purge(self, service: ServiceRef) -> int:
        """Forget one service's source items (021 purge after disconnect): objects stay, provenance of
        the removed source goes with it, effective fields are recomputed from what remains."""
        async with self.database.unit_of_work() as uow:
            session = uow.session
            items = (
                (await session.execute(select(SourceItem).where(SourceItem.service_id == service.service_id)))
                .scalars()
                .all()
            )
            ids = [item.id for item in items]
            objects = {item.object_id for item in items if item.object_id is not None}
            if not ids:
                return 0
            await session.execute(delete(FieldCandidate).where(FieldCandidate.source_item_id.in_(ids)))
            await session.execute(
                update(Image).where(Image.source_item_id.in_(ids)).values(source_item_id=None)
            )
            await session.execute(delete(SourceItem).where(SourceItem.id.in_(ids)))
            for object_id in objects:
                await self.writer.refresh(session, object_id)
            log.info("media source purged", extra={"count": len(ids)})
            return len(ids)

    async def stored_at(self, service: ServiceRef) -> dict[str, tuple[dict[str, Any], datetime, bool]]:
        async with self.database.session() as session:
            rows = (
                (await session.execute(select(SourceItem).where(SourceItem.service_id == service.service_id)))
                .scalars()
                .all()
            )
            return {r.external_id: (r.payload, r.observed_at, r.active) for r in rows}
