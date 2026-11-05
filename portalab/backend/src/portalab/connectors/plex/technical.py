"""#354: a title's technical sheet in Plex (``/library/metadata/<key>``) — when it was added, each file (its
path, size, container, length and bitrate) and each stream of it: the video (codec, resolution, dynamic
range), the audio tracks (codec, language, channels) and the subtitles (format, language, forced) — what the
team needs to answer a member's report on a title."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from portalab.capabilities.connector_sdk import ServiceHandle
from portalab.capabilities.media import TechnicalFile, TechnicalSheet, TechnicalStream, video_resolution
from portalab.connectors.http_base import HttpConnector, safe_id

KINDS: dict[int, Literal["video", "audio", "subtitle"]] = {1: "video", 2: "audio", 3: "subtitle"}


def _text(value: Any, limit: int = 120) -> str | None:
    return str(value)[:limit] if value not in (None, "") else None


def _int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _range(stream: Mapping[str, Any]) -> str | None:
    if stream.get("DOVIPresent"):
        return "Dolby Vision"
    named = stream.get("videoRangeType") or stream.get("videoRange")
    if named:
        return str(named)[:40]
    transfer = str(stream.get("colorTrc") or "").lower()
    return "HDR10" if transfer == "smpte2084" else "HLG" if transfer == "arib-std-b67" else None


def stream_of(stream: Mapping[str, Any]) -> TechnicalStream | None:
    kind = KINDS.get(_int(stream.get("streamType")) or 0)
    if kind is None:
        return None
    height = _int(stream.get("height"))
    return TechnicalStream(
        kind=kind,
        codec=_text(stream.get("codec"), 40),
        language=_text(stream.get("language") or stream.get("languageCode"), 60),
        title=_text(stream.get("extendedDisplayTitle") or stream.get("displayTitle") or stream.get("title")),
        channels=_text(stream.get("audioChannelLayout") or stream.get("channels"), 40)
        if kind == "audio"
        else None,
        resolution=video_resolution(_int(stream.get("width")), height) if kind == "video" else None,
        dynamic_range=_range(stream) if kind == "video" else None,
        bitrate=_int(stream.get("bitrate")),
        forced=bool(stream.get("forced")),
        default=bool(stream.get("default")),
    )


def sheet_of(item: Mapping[str, Any]) -> TechnicalSheet:
    files = []
    for media in item.get("Media") or []:
        if not isinstance(media, Mapping):
            continue
        for part in media.get("Part") or []:
            if not isinstance(part, Mapping):
                continue
            duration = _int(part.get("duration") or media.get("duration"))
            files.append(
                TechnicalFile(
                    path=_text(part.get("file"), 500),
                    size=_int(part.get("size")),
                    container=_text(part.get("container") or media.get("container"), 20),
                    duration_s=duration / 1000 if duration else None,
                    bitrate=_int(media.get("bitrate")),
                    streams=tuple(
                        found
                        for stream in part.get("Stream") or []
                        if isinstance(stream, Mapping) and (found := stream_of(stream)) is not None
                    ),
                )
            )
    added = _int(item.get("addedAt"))
    return TechnicalSheet(
        added_at=datetime.fromtimestamp(added, UTC) if added else None,
        files=tuple(files),
    )


class PlexTechnical:
    def __init__(self, connector: HttpConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def technical(self, external_id: str, kind: str) -> TechnicalSheet | None:
        found = await self.connector.get_json(self.service, f"/library/metadata/{safe_id(external_id)}")
        rows = (found.get("MediaContainer") or {}).get("Metadata") if isinstance(found, Mapping) else None
        item = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], Mapping) else None
        return sheet_of(item) if item is not None else None
