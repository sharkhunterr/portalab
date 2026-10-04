"""``ImageService`` (T013; R11): images are fetched **through the connector's provider** (never hot-linked),
validated (size, format, dimensions, decompression bombs) and re-encoded by Pillow (metadata stripped),
stored in the blob store and served by Media's own endpoint — no source URL or token reaches a client.
A failed fetch leaves the placeholder; it never breaks the catalog."""

import asyncio
import io
import warnings
from typing import Any
from uuid import UUID

from PIL import Image as PILImage
from PIL import UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.media import LIBRARY, SourceUnavailable, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.jobs.queue import enqueue
from portalab.core.time import Clock, utc_now
from portalab.modules.media.common import payload_hash
from portalab.modules.media.identity.resolver import MediaNotFound
from portalab.modules.media.models import Image, MediaObject, SourceItem
from portalab.modules.media.observability import log, metrics

JOB = "media.fetch_image"
MAX_BYTES = 8 * 1024 * 1024
MAX_SIDE = 8000
OUTPUT_SIDE = 1000
FORMATS = frozenset({"PNG", "JPEG", "WEBP", "GIF"})
CONTENT_TYPE = "image/jpeg"


class InvalidImage(ValueError):
    pass


def normalize_image(data: bytes) -> bytes:
    if not data or len(data) > MAX_BYTES:
        raise InvalidImage("size")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", PILImage.DecompressionBombWarning)
            with PILImage.open(io.BytesIO(data)) as probe:
                image_format, (width, height) = probe.format, probe.size
                probe.verify()
            if image_format not in FORMATS or not (1 <= width <= MAX_SIDE and 1 <= height <= MAX_SIDE):
                raise InvalidImage("format")
            with PILImage.open(io.BytesIO(data)) as image:
                image.seek(0)
                frame = image.convert("RGB")
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, PILImage.DecompressionBombError) as exc:
        raise InvalidImage("undecodable") from exc
    except PILImage.DecompressionBombWarning as exc:
        raise InvalidImage("bomb") from exc
    frame.thumbnail((OUTPUT_SIDE, OUTPUT_SIDE))
    output = io.BytesIO()
    frame.save(output, format="JPEG", quality=85, optimize=True)  # fresh file: no EXIF/ICC/comments
    return output.getvalue()


class ImageService:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        blobs: BlobStore | None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.blobs = blobs
        self.clock = clock

    async def schedule(self, session: AsyncSession, object_id: UUID) -> None:
        row = await session.get(MediaObject, object_id)
        ref = (row.effective or {}).get("image") if row is not None else None
        if ref:
            await enqueue(
                session,
                kind=JOB,
                payload={"object": str(object_id)},
                dedup_key=f"{JOB}:{object_id}:{payload_hash({'ref': ref})[:16]}",
                clock=self.clock,
            )

    def _provider(self, service_id: UUID) -> Any | None:
        try:
            providers = self.capabilities.system_providers(LIBRARY)
        except Exception:
            return None
        for registration in providers:
            if registration.instance_ref == str(service_id):
                return registration.provider
        return None

    async def fetch(self, object_id: UUID) -> bool:
        """Fetch the effective image of one object through its source's provider (job handler body)."""
        if self.blobs is None:
            return False
        async with self.database.session() as session:
            row = await session.get(MediaObject, object_id)
            if row is None:
                return False
            ref = (row.effective or {}).get("image")
            source = (row.field_provenance or {}).get("image")
            if not ref or not source:
                return False
            # one source may hold the same title twice (a film in two libraries, 4K and HD…): take the
            # item whose payload carries this image reference, preferring active ones
            candidates = list(
                (
                    await session.execute(
                        select(SourceItem)
                        .where(SourceItem.object_id == object_id, SourceItem.source_system == source)
                        .order_by(SourceItem.active.desc(), SourceItem.last_seen_at.desc())
                    )
                ).scalars()
            )
            item = next((c for c in candidates if (c.payload or {}).get("image") == ref), None) or (
                candidates[0] if candidates else None
            )
            existing = (
                await session.execute(
                    select(Image).where(Image.object_id == object_id, Image.role == "poster")
                )
            ).scalar_one_or_none()
        if item is None or (existing is not None and existing.source_ref == ref):
            return False
        provider = self._provider(item.service_id)
        if provider is None:
            # the source service is not provided in this process (yet): retried by the job queue
            raise LookupError("the image source is not available in this process")
        try:
            raw = unwrap(await asyncio.wait_for(provider.fetch_image(ref), timeout=20))
            data = normalize_image(bytes(raw))
        except (SourceUnavailable, InvalidImage, TimeoutError, ConnectionError, OSError) as exc:
            metrics.increment("media.images.failed")
            log.info("media image not fetched", extra={"reason": type(exc).__name__})
            return False
        stored = await self.blobs.put("media", data, content_type=CONTENT_TYPE)
        values = {
            "blob_key": stored.key,
            "content_hash": payload_hash({"sha": stored.key}),
            "source_ref": ref,
            "source_item_id": item.id,
            "created_at": utc_now(self.clock),
        }
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(Image)
                .values(object_id=object_id, role="poster", **values)
                .on_conflict_do_update(constraint="uq_images_object_role", set_=values)
            )
        metrics.increment("media.images.stored")
        return True

    async def run(self, payload: dict[str, object]) -> None:
        await self.fetch(UUID(str(payload["object"])))

    async def content(self, image_id: UUID) -> bytes:
        async with self.database.session() as session:
            row = await session.get(Image, image_id)
        if row is None or self.blobs is None:
            raise MediaNotFound("This image does not exist.")
        return await self.blobs.get(row.blob_key)

    async def for_object(self, session: AsyncSession, object_id: UUID) -> UUID | None:
        return (
            await session.execute(
                select(Image.id).where(Image.object_id == object_id, Image.role == "poster")
            )
        ).scalar_one_or_none()
