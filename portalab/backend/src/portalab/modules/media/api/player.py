"""HTTP API of the portal's player (027, #2).

``GET /media/{id}/player`` describes what plays (versions, tracks, markers, resume point), ``POST …/start``
starts a stream and returns its signed ticket; the browser's player then reads
``/media/player/{ticket}/session/…`` (HLS playlists and segments relayed from the media server), the
subtitle cues around the current time, and reports where it is (resume point, activity).
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from portalab.capabilities.media import (
    QUALITIES,
    PlayableItem,
    StreamMarker,
    StreamOptions,
    StreamTrack,
    StreamVersion,
)
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.media.api.router import Module, _me
from portalab.modules.media.permissions import MEDIA_PLAY

router = APIRouter(prefix="/api/v1", tags=["media"])
Player = Annotated[Principal, require(MEDIA_PLAY)]
TICKET = r"^[A-Za-z0-9_-]{20,2000}\.[A-Za-z0-9_-]{10,40}$"
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


class StreamTrackOut(BaseModel):
    id: str
    kind: str
    label: str
    language: str | None
    codec: str | None
    channels: int | None
    default: bool
    forced: bool
    selected: bool
    text: bool
    external: bool


class StreamVersionOut(BaseModel):
    index: int
    label: str
    resolution: str | None
    width: int | None
    height: int | None
    bitrate_kbps: int | None
    container: str | None
    video_codec: str | None
    audio_codec: str | None
    hdr: bool
    size: int | None
    audio: list[StreamTrackOut]
    subtitles: list[StreamTrackOut]


class StreamMarkerOut(BaseModel):
    kind: str
    start_s: float
    end_s: float
    label: str | None


class PlayableItemOut(BaseModel):
    external_id: str
    kind: str
    title: str
    duration_s: float | None
    resume_s: float
    watched: bool
    parent_title: str | None
    label: str | None
    year: int | None
    versions: list[StreamVersionOut]
    markers: list[StreamMarkerOut]
    chapters: list[StreamMarkerOut]
    previous_id: str | None
    next_id: str | None
    next_label: str | None


class PlayerInfoOut(BaseModel):
    service_id: UUID
    service_name: str | None
    linked: bool
    item: PlayableItemOut
    qualities: list[str]


class StreamStartIn(BaseModel):
    item: str = Field(min_length=1, max_length=200)
    version: int = Field(default=0, ge=0, le=20)
    quality: str = Field(default="original", max_length=20)
    audio: str | None = Field(default=None, max_length=40)
    subtitle: str | None = Field(default=None, max_length=40)
    burn: bool = False
    subtitle_size: int = Field(default=100, ge=50, le=300)
    boost: int = Field(default=100, ge=100, le=300)
    duration_s: float | None = Field(default=None, ge=0)


class StreamStartOut(BaseModel):
    ticket: str
    playlist: str  # the media playlist, under ``/api/v1/media/player/{ticket}/``
    video: str
    audio: str
    subtitles: str
    width: int | None
    height: int | None
    bitrate_kbps: int | None
    video_codec: str | None
    audio_codec: str | None


class SubtitleCueOut(BaseModel):
    start_s: float
    end_s: float
    text: str


class SubtitleCuesOut(BaseModel):
    cues: list[SubtitleCueOut]


class PlayerTimelineIn(BaseModel):
    state: str = Field(pattern=r"^(playing|paused|buffering|stopped)$")
    position_s: float = Field(ge=0)
    duration_s: float | None = Field(default=None, ge=0)


def _track(track: StreamTrack) -> StreamTrackOut:
    return StreamTrackOut(
        id=track.id,
        kind=track.kind,
        label=track.label,
        language=track.language,
        codec=track.codec,
        channels=track.channels,
        default=track.default,
        forced=track.forced,
        selected=track.selected,
        text=track.text,
        external=track.external,
    )


def _version(version: StreamVersion) -> StreamVersionOut:
    return StreamVersionOut(
        index=version.index,
        label=version.label,
        resolution=version.resolution,
        width=version.width,
        height=version.height,
        bitrate_kbps=version.bitrate_kbps,
        container=version.container,
        video_codec=version.video_codec,
        audio_codec=version.audio_codec,
        hdr=version.hdr,
        size=version.size,
        audio=[_track(t) for t in version.audio],
        subtitles=[_track(t) for t in version.subtitles],
    )


def _marker(marker: StreamMarker) -> StreamMarkerOut:
    return StreamMarkerOut(kind=marker.kind, start_s=marker.start_s, end_s=marker.end_s, label=marker.label)


def _playable(item: PlayableItem) -> PlayableItemOut:
    return PlayableItemOut(
        external_id=item.external_id,
        kind=item.kind,
        title=item.title,
        duration_s=item.duration_s,
        resume_s=item.resume_s,
        watched=item.watched,
        parent_title=item.parent_title,
        label=item.label,
        year=item.year,
        versions=[_version(v) for v in item.versions],
        markers=[_marker(m) for m in item.markers],
        chapters=[_marker(m) for m in item.chapters],
        previous_id=item.previous_id,
        next_id=item.next_id,
        next_label=item.next_label,
    )


@router.get("/media/{object_id}/player", response_model=PlayerInfoOut)
async def player_info(
    principal: Player,
    object_id: UUID,
    module: Module,
    item: Annotated[str | None, Query(max_length=200, pattern=r"^[A-Za-z0-9_-]+$")] = None,
) -> PlayerInfoOut:
    info = await module.player.info(_me(principal), object_id, item)
    return PlayerInfoOut(
        service_id=info.service_id,
        service_name=info.service_name,
        linked=info.linked,
        item=_playable(info.item),
        qualities=info.qualities,
    )


@router.post("/media/{object_id}/player/start", response_model=StreamStartOut)
async def player_start(
    principal: Player, object_id: UUID, body: StreamStartIn, module: Module
) -> StreamStartOut:
    options = StreamOptions(
        version=body.version,
        quality=body.quality if body.quality in QUALITIES else "original",
        audio=body.audio,
        subtitle=body.subtitle,
        burn=body.burn,
        subtitle_size=body.subtitle_size,
        boost=body.boost,
    )
    ticket, started = await module.player.start(
        _me(principal), object_id, body.item, options, body.duration_s
    )
    return StreamStartOut(
        ticket=ticket,
        playlist=started.playlist,
        video=started.video,
        audio=started.audio,
        subtitles=started.subtitles,
        width=started.width,
        height=started.height,
        bitrate_kbps=started.bitrate_kbps,
        video_codec=started.video_codec,
        audio_codec=started.audio_codec,
    )


@router.get("/media/player/{ticket}/subtitles", response_model=SubtitleCuesOut)
async def player_subtitles(
    principal: Player,
    module: Module,
    ticket: Annotated[str, Path(pattern=TICKET)],
    at: Annotated[float, Query(ge=0)] = 0.0,
    seek: bool = False,
) -> SubtitleCuesOut:
    cues = await module.player.subtitles(_me(principal), ticket, at, seek=seek)
    return SubtitleCuesOut(cues=[SubtitleCueOut(start_s=c.start_s, end_s=c.end_s, text=c.text) for c in cues])


@router.post("/media/player/{ticket}/timeline", status_code=status.HTTP_204_NO_CONTENT)
async def player_timeline(
    principal: Player, module: Module, ticket: Annotated[str, Path(pattern=TICKET)], body: PlayerTimelineIn
) -> None:
    await module.player.report(_me(principal), ticket, body.state, body.position_s, body.duration_s)


@router.post("/media/player/{ticket}/stop", status_code=status.HTTP_204_NO_CONTENT)
async def player_stop(
    principal: Player, module: Module, ticket: Annotated[str, Path(pattern=TICKET)]
) -> None:
    await module.player.stop(_me(principal), ticket)


@router.get("/media/player/{ticket}/session/{path:path}", include_in_schema=False)
async def player_stream(
    principal: Player, module: Module, ticket: Annotated[str, Path(pattern=TICKET)], path: str
) -> StreamingResponse:
    """A playlist or segment of the stream, relayed as the media server sends it."""
    stack = AsyncExitStack()
    body = await module.player.open(_me(principal), ticket, f"session/{path}", stack)

    async def relay() -> AsyncIterator[bytes]:
        try:
            async for chunk in body.chunks:
                yield chunk
        finally:
            await stack.aclose()

    headers = dict(NO_STORE)
    if body.length is not None:
        headers["Content-Length"] = str(body.length)
    return StreamingResponse(relay(), media_type=body.content_type, headers=headers)
