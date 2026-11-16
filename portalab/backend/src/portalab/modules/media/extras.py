"""Issue 465: a title's videos and extra pictures — trailers, teasers, featurettes, behind the scenes, a
game's gameplay videos; backdrops, stills, screenshots, artworks — gathered from every service that knows some
(TMDB, TheTVDB, fanart.tv, Radarr, Plex for films and series; IGDB, RomM for games).

Each service is asked by the title's ids, the one holding it also by its own item. What they tell is kept a
few hours per title and language. Pictures are fetched by the portal, decoded and saved afresh, then served
from the portal: members' browsers never call those services. A YouTube video is shown by its picture
(fetched the same way) and played by YouTube's privacy-enhanced player only when the member asks; a media
server's extra is played by the portal's own player.
"""

import asyncio
import time
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.connector_http import ConnectorHttpClient, ConnectorHttpError
from portalab.capabilities.media import (
    EXTRA_VIDEO_KINDS,
    EXTRAS,
    YOUTUBE_ID,
    ExtraImage,
    ExtraVideo,
    MediaExtras,
    unwrap,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.modules.media.images.service import InvalidImage, normalize_image
from portalab.modules.media.models import ExternalId, MediaObject, SourceItem
from portalab.modules.media.observability import log, metrics

KINDS = ("movie", "series", "game")
TIMEOUT_S = 10  # each service's answer
IMAGE_TIMEOUT_S = 20
KEPT_S = 6 * 3600  # what the services told of a title
KEPT_AFTER_FAILURE_S = 5 * 60  # … when one of them did not answer: asked again sooner
KEPT_TITLES = 500
KEPT_PICTURES = 2000
VIDEOS = 40
IMAGES = 40
PREVIEW_SIDE = 480
FULL_SIDE = 1920
YOUTUBE_PICTURES = "https://i.ytimg.com"
# videos in this order of kinds (a game's gameplay right after its trailers)
VIDEO_ORDER = {kind: i for i, kind in enumerate(("trailer", "teaser", "gameplay", *EXTRA_VIDEO_KINDS))}
IMAGE_ORDER = {kind: i for i, kind in enumerate(("backdrop", "fanart", "still", "screenshot", "artwork"))}


class ExtraNotFound(LookupError):
    """No such video or picture for this title (or no longer: what the services tell has changed)."""


@dataclass(frozen=True, slots=True)
class Video:
    service: str
    video: ExtraVideo


@dataclass(frozen=True, slots=True)
class Picture:
    service: str
    image: ExtraImage


@dataclass(frozen=True, slots=True)
class TitleExtras:
    videos: tuple[Video, ...] = ()
    images: tuple[Picture, ...] = ()


def _language_rank(language: str | None, member: str) -> int:
    if language == member:
        return 0
    if language is None:
        return 1
    return 2 if language == "en" else 3


def arrange(found: Sequence[tuple[str, MediaExtras]], language: str) -> TitleExtras:
    """What every service told, as one list of videos and one of pictures: each YouTube video once (what
    each telling knows of it together), sorted by kind, then the member's language first, the media
    server's own first, the official ones first; pictures sorted by kind, each once."""
    member = language.split("-")[0].lower()
    videos: dict[tuple[str, str], Video] = {}
    for service, extras in found:
        for video in extras.videos:
            if video.site == "youtube" and not YOUTUBE_ID.fullmatch(video.key):
                continue
            key = (video.site, video.key if video.site == "youtube" else f"{service}/{video.key}")
            kept = videos.get(key)
            if kept is None:
                videos[key] = Video(service, video)
            else:  # one video told twice: what each telling knows, together
                first = kept.video
                videos[key] = Video(
                    kept.service,
                    replace(
                        first,
                        name=first.name or video.name,
                        kind=video.kind if first.kind == "other" else first.kind,
                        language=first.language or video.language,
                        official=first.official or video.official,
                        duration_s=first.duration_s or video.duration_s,
                    ),
                )
    ordered_videos = sorted(
        videos.values(),
        key=lambda v: (
            VIDEO_ORDER.get(v.video.kind, len(VIDEO_ORDER)),
            _language_rank(v.video.language, member),
            v.video.site != "service",
            not v.video.official,
        ),
    )
    pictures: dict[tuple[str, str], Picture] = {}
    for service, extras in found:
        for image in extras.images:
            pictures.setdefault((service, image.ref), Picture(service, image))
    ordered_pictures = sorted(
        pictures.values(),
        key=lambda p: (
            IMAGE_ORDER.get(p.image.kind, len(IMAGE_ORDER)),
            p.image.lang is not None and p.image.lang != member,
        ),
    )
    return TitleExtras(tuple(ordered_videos[:VIDEOS]), tuple(ordered_pictures[:IMAGES]))


class MediaExtrasService:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        *,
        blobs: BlobStore | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.blobs = blobs
        self.now = now
        self._titles: OrderedDict[tuple[UUID, str], tuple[float, TitleExtras]] = OrderedDict()
        self._pictures: OrderedDict[tuple[str, ...], str] = OrderedDict()
        self.youtube = ConnectorHttpClient(
            YOUTUBE_PICTURES, timeout_seconds=15, max_response_bytes=2 * 1024 * 1024, retries=1
        )

    # --- what the services tell -----------------------------------------------------------------------
    async def of(self, object_id: UUID, language: str) -> TitleExtras:
        key = (object_id, language)
        kept = self._titles.get(key)
        if kept is not None and kept[0] > self.now():
            self._titles.move_to_end(key)
            return kept[1]
        extras, complete = await self._gather(object_id, language)
        self._titles[key] = (self.now() + (KEPT_S if complete else KEPT_AFTER_FAILURE_S), extras)
        while len(self._titles) > KEPT_TITLES:
            self._titles.popitem(last=False)
        return extras

    async def _gather(self, object_id: UUID, language: str) -> tuple[TitleExtras, bool]:
        try:
            registrations = list(self.capabilities.system_providers(EXTRAS))
        except Exception:
            return TitleExtras(), True
        if not registrations:
            return TitleExtras(), True
        async with self.database.session() as session:
            obj = await session.get(MediaObject, object_id)
            if obj is None or obj.status != "active" or obj.kind not in KINDS:
                return TitleExtras(), True
            ids: dict[str, str] = {
                scheme: value
                for scheme, value in (
                    await session.execute(
                        select(ExternalId.scheme, ExternalId.value).where(ExternalId.object_id == object_id)
                    )
                ).all()
            }
            held: dict[str, str] = {}
            for service_id, external_id in (
                await session.execute(
                    select(SourceItem.service_id, SourceItem.external_id)
                    .where(SourceItem.object_id == object_id, SourceItem.active.is_(True))
                    .order_by(SourceItem.last_seen_at.desc())
                )
            ).all():
                held.setdefault(str(service_id), external_id)
        kind = obj.kind
        complete = True

        async def ask(registration: Any) -> tuple[str, MediaExtras] | None:
            nonlocal complete
            service = str(registration.instance_ref)
            try:
                asked = registration.provider.extras(kind, ids, held.get(service), language)
                told = unwrap(await asyncio.wait_for(asked, timeout=TIMEOUT_S))
            except Exception as exc:
                complete = False
                metrics.increment("media.extras.error")
                log.info("extras of %s from %s failed: %s", object_id, service, type(exc).__name__)
                return None
            return (service, told) if isinstance(told, MediaExtras) else None

        found = [f for f in await asyncio.gather(*(ask(r) for r in registrations)) if f is not None]
        return arrange(found, language), complete

    async def service_video(self, object_id: UUID, key: str) -> bool:
        """Issue 466: whether a media server's item is one of this title's extras (it may then be played
        through the title, as its own episodes are) — as told in any language (a media server's extras do
        not depend on it)."""
        told = [kept for (title, _), (_, kept) in self._titles.items() if title == object_id]
        for extras in told or [await self.of(object_id, "en")]:
            if any(v.video.site == "service" and v.video.key == key for v in extras.videos):
                return True
        return False

    # --- pictures ----------------------------------------------------------------------------------------
    def _provider(self, service: str) -> Any:
        for registration in self.capabilities.system_providers(EXTRAS):
            if str(registration.instance_ref) == service:
                return registration.provider
        raise ExtraNotFound("the service telling it is gone")

    async def image(self, object_id: UUID, index: int, language: str, *, preview: bool) -> bytes:
        extras = await self.of(object_id, language)
        if not 0 <= index < len(extras.images):
            raise ExtraNotFound("no such picture")
        picture = extras.images[index]
        return await self._picture(
            (picture.service, picture.image.ref, "preview" if preview else "full"),
            lambda: self._provider(picture.service).extra_image(picture.image.ref, preview),
            PREVIEW_SIDE if preview else FULL_SIDE,
        )

    async def video_picture(self, object_id: UUID, index: int, language: str) -> bytes:
        extras = await self.of(object_id, language)
        if not 0 <= index < len(extras.videos):
            raise ExtraNotFound("no such video")
        found = extras.videos[index]
        video = found.video
        if video.site == "youtube":
            return await self._picture(("youtube", video.key), lambda: self._youtube(video.key), PREVIEW_SIDE)
        if not video.picture:
            raise ExtraNotFound("this video has no picture")
        ref = video.picture
        return await self._picture(
            (found.service, ref, "video"),
            lambda: self._provider(found.service).extra_image(ref, True),
            PREVIEW_SIDE,
        )

    async def _youtube(self, key: str) -> bytes:
        if not YOUTUBE_ID.fullmatch(key):
            raise ExtraNotFound("not a YouTube video")
        try:
            response = await self.youtube.get(f"/vi/{key}/mqdefault.jpg")
        except ConnectorHttpError as exc:
            raise ConnectionError(str(exc)) from exc
        if response.status_code >= 400:
            raise ConnectionError(f"YouTube's pictures answered HTTP {response.status_code}")
        return response.content

    async def _picture(self, key: tuple[str, ...], fetch: Callable[[], Any], side: int) -> bytes:
        """A picture fetched once, decoded and saved afresh (an untrusted file never reaches a browser
        as it came), then served from the blob store."""
        stored = self._pictures.get(key)
        if stored is not None and self.blobs is not None:
            try:
                return await self.blobs.get(stored)
            except Exception:
                self._pictures.pop(key, None)
        raw = unwrap(await asyncio.wait_for(fetch(), timeout=IMAGE_TIMEOUT_S))
        try:
            data = await asyncio.to_thread(normalize_image, raw, side)
        except InvalidImage as exc:
            raise ConnectionError("the service gave no usable picture") from exc
        if self.blobs is not None:
            blob = await self.blobs.put("media-extras", data, content_type="image/jpeg")
            self._pictures[key] = blob.key
            while len(self._pictures) > KEPT_PICTURES:
                self._pictures.popitem(last=False)
        return data
