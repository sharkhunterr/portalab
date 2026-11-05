"""#354: a title's technical sheet in Jellyfin (``/Items`` with its media sources) — when it was added, each
file and its streams (video, audio tracks, subtitles), for the team answering a member's report."""

from collections.abc import Mapping
from typing import Any, Literal

from portalab.capabilities.connector_sdk import ServiceHandle
from portalab.capabilities.media import TechnicalFile, TechnicalSheet, TechnicalStream, video_resolution
from portalab.connectors.http_base import HttpConnector, parse_time, safe_id

KINDS: dict[str, Literal["video", "audio", "subtitle"]] = {
    "Video": "video",
    "Audio": "audio",
    "Subtitle": "subtitle",
}
TICKS = 10_000_000


def _text(value: Any, limit: int = 120) -> str | None:
    return str(value)[:limit] if value not in (None, "") else None


def _int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def stream_of(stream: Mapping[str, Any]) -> TechnicalStream | None:
    kind = KINDS.get(str(stream.get("Type") or ""))
    if kind is None:
        return None
    height = _int(stream.get("Height"))
    bitrate = _int(stream.get("BitRate"))
    return TechnicalStream(
        kind=kind,
        codec=_text(stream.get("Codec"), 40),
        language=_text(stream.get("Language"), 60),
        title=_text(stream.get("DisplayTitle") or stream.get("Title")),
        channels=_text(stream.get("ChannelLayout") or stream.get("Channels"), 40)
        if kind == "audio"
        else None,
        resolution=video_resolution(_int(stream.get("Width")), height) if kind == "video" else None,
        dynamic_range=_text(stream.get("VideoRangeType") or stream.get("VideoRange"), 40)
        if kind == "video"
        else None,
        bitrate=bitrate // 1000 if bitrate else None,
        forced=bool(stream.get("IsForced")),
        default=bool(stream.get("IsDefault")),
    )


def sheet_of(item: Mapping[str, Any]) -> TechnicalSheet:
    files = []
    for source in item.get("MediaSources") or []:
        if not isinstance(source, Mapping):
            continue
        ticks = _int(source.get("RunTimeTicks"))
        bitrate = _int(source.get("Bitrate"))
        files.append(
            TechnicalFile(
                path=_text(source.get("Path"), 500),
                size=_int(source.get("Size")),
                container=_text(source.get("Container"), 20),
                duration_s=ticks / TICKS if ticks else None,
                bitrate=bitrate // 1000 if bitrate else None,
                streams=tuple(
                    found
                    for stream in source.get("MediaStreams") or []
                    if isinstance(stream, Mapping) and (found := stream_of(stream)) is not None
                ),
            )
        )
    return TechnicalSheet(added_at=parse_time(item.get("DateCreated")), files=tuple(files))


class JellyfinTechnical:
    def __init__(self, connector: HttpConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def technical(self, external_id: str, kind: str) -> TechnicalSheet | None:
        found = await self.connector.get_json(
            self.service,
            "/Items",
            Ids=safe_id(external_id),
            Fields="MediaSources,DateCreated",
            Recursive="true",
        )
        rows = found.get("Items") if isinstance(found, Mapping) else None
        item = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], Mapping) else None
        return sheet_of(item) if item is not None else None
