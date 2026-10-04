"""``jellyfin`` connector: Jellyfin (and Emby, same API) media servers.

* ``media.library`` (sync): movies, series, seasons, episodes, music albums and tracks, books — paged
  through ``/Items`` with provider ids (TMDB/IMDb/TVDB/MusicBrainz) so Media can merge sources.
* ``media.playback``: live sessions (``/Sessions``) and, per user, recently played items.
* ``service.health_probe``: an authenticated ``/System/Info`` round trip.

Authentication uses an API key created in *Dashboard → API Keys*, sent as
``Authorization: MediaBrowser Token="…"`` (the header every current Jellyfin accepts).
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import datetime
from typing import Any

from portalab.capabilities.connector_sdk import (
    CapabilityBinding,
    ServiceHandle,
    SourceRecord,
    SyncContext,
    SyncProgress,
)
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import (
    LIBRARY,
    PLAYBACK,
    SourceHistoryItem,
    SourcePlayback,
)
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.http_base import HttpConnector, _Probe, binding, parse_time, safe_id

PAGE = 200
TICKS = 10_000_000  # 100 ns ticks per second
KINDS = {
    "Movie": "movie",
    "Series": "series",
    "Season": "season",
    "Episode": "episode",
    "MusicAlbum": "album",
    "Audio": "track",
    "Book": "book",
    "AudioBook": "book",
}
IDS = {"Tmdb": "tmdb", "Imdb": "imdb", "Tvdb": "tvdb", "MusicBrainzAlbum": "musicbrainz", "Isbn": "isbn"}
FIELDS = "ProviderIds,Overview,Genres,ProductionYear,OriginalTitle,People,DateCreated,ParentId"


def _ids(item: Mapping[str, Any]) -> dict[str, str]:
    raw = item.get("ProviderIds") or {}
    return {IDS[k]: str(v) for k, v in raw.items() if k in IDS and v}


def _parent(item: Mapping[str, Any], kind: str) -> str | None:
    value = {
        "season": item.get("SeriesId"),
        "episode": item.get("SeasonId") or item.get("SeriesId"),
        "track": item.get("AlbumId"),
    }.get(kind)
    return str(value) if value else None


def _seconds(ticks: Any) -> float | None:
    return round(ticks / TICKS, 1) if isinstance(ticks, int | float) and ticks > 0 else None


class JellyfinConnector(HttpConnector):
    key = "jellyfin"
    name = "Jellyfin"
    description = "Your Jellyfin (or Emby) media server: films, series, music and what is playing."
    icon = "film"
    category = "media"
    provides: Sequence[CapabilityBinding] = (
        binding(LIBRARY, syncable=True),
        binding(PLAYBACK),
        binding(HEALTH_PROBE),
    )
    status_path = "/System/Info"
    public_path = "/System/Info/Public"

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        token = service.secrets.get("api_key", "")
        return {
            "Authorization": f'MediaBrowser Client="Portalab", Device="Portalab", DeviceId="portalab", '
            f'Version="1.0", Token="{token}"'
        }

    def describe(self, status: Any) -> str:
        if not isinstance(status, Mapping) or "Version" not in status:
            raise InvalidPayload("not a Jellyfin system info")
        return f"{status.get('ServerName') or self.name} (Jellyfin {status['Version']})"

    def looks_like_us(self, public: Any) -> bool:
        return isinstance(public, Mapping) and "Version" in public and "Id" in public

    async def sync(
        self, ctx: SyncContext, cursor: Mapping[str, Any] | None
    ) -> AsyncIterator[SourceRecord | SyncProgress]:
        service = ctx.service
        start = 0
        while True:
            page = await self.get_json(
                service,
                "/Items",
                Recursive="true",
                IncludeItemTypes=",".join(KINDS),
                Fields=FIELDS,
                SortBy="SortName",
                StartIndex=start,
                Limit=PAGE,
            )
            if not isinstance(page, Mapping) or not isinstance(page.get("Items"), list):
                raise InvalidPayload("unexpected /Items payload")
            for item in page["Items"]:
                kind = KINDS.get(str(item.get("Type")))
                if kind is None or not item.get("Name"):
                    continue
                item_id = safe_id(item["Id"])
                payload = {
                    "title": str(item["Name"])[:500],
                    "original_title": item.get("OriginalTitle"),
                    "ids": _ids(item),
                    "parent": _parent(item, kind),
                    "position": item.get("IndexNumber"),
                    "year": item.get("ProductionYear"),
                    "overview": (item.get("Overview") or "")[:5000] or None,
                    "genres": list(item.get("Genres") or [])[:30],
                    "people": [p.get("Name") for p in item.get("People") or [] if p.get("Name")][:50],
                    "duration_s": _seconds(item.get("RunTimeTicks")),
                    "image": item_id if (item.get("ImageTags") or {}).get("Primary") else None,
                }
                yield self.record(service, item_id, kind, payload, parse_time(item.get("DateCreated")))
            start += len(page["Items"])
            if not page["Items"] or start >= int(page.get("TotalRecordCount") or 0):
                break
        yield SyncProgress(cursor={"items": start})

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == LIBRARY:
            return _Library(self, service)
        if capability == PLAYBACK:
            return _Playback(self, service)
        if capability == HEALTH_PROBE:
            return _Probe(self, service)
        return None


class _Library:
    def __init__(self, connector: JellyfinConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def fetch_image(self, ref: str) -> bytes:
        return await self.connector.get_bytes(
            self.service, f"/Items/{safe_id(ref)}/Images/Primary", maxWidth=600, quality=85
        )


class _Playback:
    def __init__(self, connector: JellyfinConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service

    async def now_playing(self) -> Sequence[SourcePlayback]:
        sessions = await self.connector.get_json(self.service, "/Sessions", ActiveWithinSeconds=120)
        if not isinstance(sessions, list):
            raise InvalidPayload("unexpected /Sessions payload")
        playing = []
        for session in sessions:
            item = session.get("NowPlayingItem")
            if not item:
                continue
            state = session.get("PlayState") or {}
            playing.append(
                SourcePlayback(
                    session_key=str(session.get("Id")),
                    state="paused" if state.get("IsPaused") else "playing",
                    kind=KINDS.get(str(item.get("Type")), "movie"),
                    title=str(item.get("Name") or "?"),
                    external_user_id=session.get("UserId"),
                    item_external_id=item.get("Id"),
                    ids=_ids(item),
                    position_s=_seconds(state.get("PositionTicks")) or 0.0,
                    duration_s=_seconds(item.get("RunTimeTicks")),
                    device=session.get("DeviceName"),
                )
            )
        return playing

    async def recent_history(self, since: datetime) -> Sequence[SourceHistoryItem]:
        users = await self.connector.get_json(self.service, "/Users")
        if not isinstance(users, list):
            raise InvalidPayload("unexpected /Users payload")
        history: list[SourceHistoryItem] = []
        for user in users[:50]:
            user_id = safe_id(user.get("Id"))
            page = await self.connector.get_json(
                self.service,
                "/Items",
                userId=user_id,
                Recursive="true",
                Filters="IsPlayed",
                SortBy="DatePlayed",
                SortOrder="Descending",
                IncludeItemTypes="Movie,Episode,Audio",
                Fields="ProviderIds",
                Limit=50,
            )
            for item in (page or {}).get("Items", []):
                played = parse_time((item.get("UserData") or {}).get("LastPlayedDate"))
                if played is None or played < since:
                    continue
                duration = _seconds(item.get("RunTimeTicks"))
                history.append(
                    SourceHistoryItem(
                        external_user_id=user_id,
                        kind=KINDS.get(str(item.get("Type")), "movie"),
                        title=str(item.get("Name") or "?"),
                        occurred_at=played,
                        position_s=duration or 0.0,
                        duration_s=duration,
                        item_external_id=item.get("Id"),
                        ids=_ids(item),
                    )
                )
        return sorted(history, key=lambda h: h.occurred_at)
