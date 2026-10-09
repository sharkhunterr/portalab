"""Media capability catalog (spec 024 R5, contracts/media-contracts.md), implemented by connectors.

* ``media.library`` (sync only): connectors yield ``SourceRecord(kind=<media type>, external_id, payload)``
  whose payload follows :class:`LibraryPayload`; Media's ``RecordSink`` ingests them. The per-service
  provider only serves images (``fetch_image``) so no source URL or token ever reaches a client.
* ``media.playback`` (live): what is playing now and recent history on one service.
* ``request.service`` (live + sync): submit/track requests; sync yields :class:`RequestPayload` records.
* ``service.accounts`` (027): the accounts of one service, matched with portal members.
* ``media.activity_history`` (027): the full play/read history of one service, paged — backfilled once,
  then followed incrementally; sources reporting the same plays (Plex and Tautulli) share a ``family``
  so the portal keeps one row per play, from the richest source.
* ``media.calendar`` (027): upcoming releases (Radarr, Sonarr…).
* ``media.downloads`` (027): what a download manager is fetching or importing now (Radarr, Sonarr queues).
* ``media.metadata`` (027): a metadata provider (TMDB…) enriching catalog objects — backdrop, cast,
  collection, budget, revenue, genres… — and serving its images.
* ``media.streaming`` (027, #2): play a title inside the portal, the service deciding between direct
  stream and transcoding (Plex's universal transcoder) — HLS relayed by the portal, so no service address
  or token ever reaches a browser; played as the member's own account on the service.

Providers are bound to one service (``instance_ref`` = the service id) and are usually wrapped by the 001
isolation guard, so calls may return a :class:`~portalab.capabilities.results.CapabilityResult`;
:func:`unwrap` turns that into a value or :class:`SourceUnavailable`. No provider-specific code lives in
the core: a Plex, Jellyfin or Sonarr connector only maps its API onto these shapes.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.registry import CapabilitySpec
from portalab.capabilities.results import CapabilityResult

LIBRARY = "media.library"
PLAYBACK = "media.playback"
REQUESTS = "request.service"
ACCOUNTS = "service.accounts"
ACTIVITY_HISTORY = "media.activity_history"
CALENDAR = "media.calendar"
METADATA = "media.metadata"
DOWNLOADS = "media.downloads"
ACQUISITION = "media.acquisition"  # 027: what a download manager knows of one title (Radarr, Sonarr)
DOWNLOAD_CLIENTS = "media.download_clients"  # 027: torrent clients (qBittorrent, Deluge)
ITEM_LINKS = "media.item_links"  # 027: where a title opens in its service (Plex, Jellyfin, Grimmory…)
STREAMING = "media.streaming"  # 027 (#2): the portal's own player, fed by the service's transcoder
ACTIVITY_KINDS: tuple[str, ...] = ("movie", "episode", "live", "track", "book", "audiobook", "other")

PlaybackState = Literal["playing", "paused", "buffering", "stopped"]
RequestState = Literal["pending", "approved", "declined", "processing", "available", "failed", "cancelled"]
REQUEST_STATES: tuple[str, ...] = (
    "pending",
    "approved",
    "declined",
    "processing",
    "available",
    "failed",
    "cancelled",
)
ID_SCHEMES = ("tmdb", "imdb", "tvdb", "isbn", "igdb", "musicbrainz", "anilist", "openlibrary")


class SourceUnavailable(Exception):
    """A per-service provider did not answer (outage, timeout, auth, invalid payload)."""

    def __init__(self, state: str = "unavailable") -> None:
        super().__init__(state)
        self.state = state


def unwrap(value: Any) -> Any:
    if isinstance(value, CapabilityResult):
        if not value.has_data:
            raise SourceUnavailable(value.state)
        return value.value  # type: ignore[attr-defined]
    return value


class LibraryPayload(BaseModel):
    """Payload of a ``media.library`` record (strong ids anchor identity; everything else is metadata)."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=500)
    original_title: str | None = Field(default=None, max_length=500)
    ids: dict[str, str] = Field(default_factory=dict)
    parent: str | None = Field(default=None, max_length=200)  # external id of the parent item
    position: int | None = None  # season/episode/track number within the parent
    year: int | None = Field(default=None, ge=1800, le=2200)
    overview: str | None = Field(default=None, max_length=5000)
    genres: list[str] = Field(default_factory=list, max_length=30)
    people: list[str] = Field(default_factory=list, max_length=50)
    language: str | None = Field(default=None, max_length=16)
    duration_s: float | None = Field(default=None, ge=0)
    pages: int | None = Field(default=None, ge=0)
    image: str | None = Field(default=None, max_length=300)  # opaque ref fetched through the provider
    available: bool = True
    # 027: release date (a film's, a book's) or air date (an episode's), for « Recent releases »
    released: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    # 027: a book's series and publisher (Grimmory)
    series: str | None = Field(default=None, max_length=200)
    series_position: float | None = Field(default=None, ge=0, le=100_000)
    publisher: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=40)  # moods and themes (Grimmory)
    # 027: the video file's resolution (``4k``, ``1080p``, ``720p``, ``sd``) — statistics' quality fallback
    resolution: str | None = Field(default=None, pattern=r"^(4k|1080p|720p|sd)$")
    # 027: which copy this item is when a service holds several of one title (a game per platform/region)
    variant: str | None = Field(default=None, max_length=200)
    platform: str | None = Field(default=None, max_length=120)  # 027: a game's console or system


class RequestPayload(BaseModel):
    """Payload of a ``request.service`` sync record (``external_id`` = the source request id)."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=500)
    kind: str = Field(min_length=1, max_length=40)
    ids: dict[str, str] = Field(default_factory=dict)
    state: RequestState = "pending"
    source_state: str = Field(default="", max_length=60)
    requester: str | None = Field(default=None, max_length=200)  # external user id on the service
    available_at: datetime | None = None  # 027: when the media became available (time to availability)


@dataclass(frozen=True, slots=True)
class SourcePlayback:
    session_key: str
    state: PlaybackState
    kind: str
    title: str
    external_user_id: str | None = None
    item_external_id: str | None = None
    ids: Mapping[str, str] = field(default_factory=dict)
    position_s: float = 0.0
    duration_s: float | None = None
    device: str | None = None


@dataclass(frozen=True, slots=True)
class SourceHistoryItem:
    external_user_id: str
    kind: str
    title: str
    occurred_at: datetime
    position_s: float
    duration_s: float | None = None
    item_external_id: str | None = None
    ids: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceRequest:
    external_request_id: str
    state: RequestState
    source_state: str = ""


@runtime_checkable
class MediaLibrary(Protocol):
    async def fetch_image(self, ref: str) -> bytes: ...


@runtime_checkable
class MediaPlayback(Protocol):
    async def now_playing(self) -> Sequence[SourcePlayback]: ...

    async def recent_history(self, since: datetime) -> Sequence[SourceHistoryItem]: ...


@runtime_checkable
class RequestService(Protocol):
    async def submit(
        self, ids: Mapping[str, str], kind: str, title: str, requester: str | None
    ) -> SourceRequest: ...

    async def status(self, external_request_id: str) -> SourceRequest: ...


@dataclass(frozen=True, slots=True)
class ServiceAccount:
    """An account on a connected service (027): what an administrator matches with a portal member."""

    external_id: str
    username: str | None = None
    display_name: str | None = None
    email: str | None = None


@runtime_checkable
class ServiceAccounts(Protocol):
    async def list_accounts(self) -> Sequence[ServiceAccount]: ...


def resolution_of(raw: object) -> str | None:
    """027: a resolution as a source names it (« 4k », « 2160 », « 1080 », « 720p », « 480 », « sd »…) or a
    frame height, as ``4k``, ``1080p``, ``720p`` or ``sd``."""
    text = str(raw or "").strip().lower()
    if not text:
        return None
    if "4k" in text or "uhd" in text:
        return "4k"
    digits = "".join(ch for ch in text if ch.isdigit())
    height = int(digits) if digits else None
    if height is None:
        return "sd" if text == "sd" else None
    if height >= 1440:
        return "4k"
    if height >= 900:
        return "1080p"
    if height >= 600:
        return "720p"
    return "sd"


@dataclass(frozen=True, slots=True)
class SourceActivity:
    """One play or reading session as the source recorded it (027, Telemetra-style raw history)."""

    ref: str  # unique id of the play on the source
    external_user_id: str
    kind: str  # one of ACTIVITY_KINDS
    title: str
    started_at: datetime
    stopped_at: datetime | None = None
    watched_s: float = 0.0  # time actually spent
    duration_s: float | None = None  # length of the item
    progress: float | None = None  # 0..1 reached at the end of the session
    item_external_id: str | None = None
    parent_title: str | None = None  # series, album, author
    ids: Mapping[str, str] = field(default_factory=dict)
    year: int | None = None
    device: str | None = None
    platform: str | None = None
    family: str | None = None  # sources reporting the same plays share it (``plex`` for Plex + Tautulli)
    priority: int = 10  # within a family, the higher source wins
    # 027: how it was streamed (``direct``, ``copy`` — direct stream —, ``transcode``) and the resolution
    # played (``4k``, ``1080p``, ``720p``, ``sd``), when the source tells
    stream: str | None = None
    quality: str | None = None


@dataclass(frozen=True, slots=True)
class ActivityPage:
    items: Sequence[SourceActivity]
    cursor: str | None = None  # pass it back for the next page; ``None`` when exhausted
    total: int | None = None  # how far the whole history goes, when the source tells (027 progress bar)
    position: int | None = None  # where this page ends, in the unit of ``total``


@runtime_checkable
class ActivityHistory(Protocol):
    async def history(self, *, since: datetime | None, cursor: str | None) -> ActivityPage: ...


@dataclass(frozen=True, slots=True)
class SourceRelease:
    """An upcoming (or just released) item announced by a service (027)."""

    external_id: str
    kind: str  # movie, episode
    title: str
    release_at: datetime
    release_type: str = "release"  # cinema, digital, physical, air
    parent_title: str | None = None
    season: int | None = None
    episode: int | None = None
    ids: Mapping[str, str] = field(default_factory=dict)
    available: bool = False
    overview: str | None = None


@runtime_checkable
class ReleaseCalendar(Protocol):
    async def upcoming(self, start: datetime, end: datetime) -> Sequence[SourceRelease]: ...


@dataclass(frozen=True, slots=True)
class SourceDownload:
    """An item a download manager is working on (027): queued, downloading or importing."""

    external_id: str
    kind: str  # movie, episode
    title: str
    status: str  # queued, downloading, importing, paused, warning, failed
    progress: float  # 0..1
    ids: Mapping[str, str] = field(default_factory=dict)
    parent_title: str | None = None
    season: int | None = None
    episode: int | None = None
    eta: datetime | None = None
    # 027: what the request journey shows — the client's name and id (a torrent hash), the release, why
    # it waits (« manual import needed », a client error…)
    download_id: str | None = None
    client: str | None = None
    release: str | None = None
    attention: str | None = None  # import_blocked | import_pending | failed | warning
    messages: tuple[str, ...] = ()
    size: int | None = None


@runtime_checkable
class DownloadQueue(Protocol):
    async def queue(self) -> Sequence[SourceDownload]: ...


@dataclass(frozen=True, slots=True)
class AcquisitionEvent:
    """One step a download manager went through for a title: grabbed, failed, imported, deleted…"""

    event: str  # grabbed | failed | imported | deleted | renamed | ignored
    at: datetime
    release: str | None = None
    client: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class SourceAcquisition:
    """027: where a download manager stands on one title (Radarr's film, Sonarr's series)."""

    service_name: str
    tracked: bool
    monitored: bool = False
    has_file: bool = False
    status: str | None = None  # announced | inCinemas | released | continuing | ended | upcoming
    searchable: bool | None = None  # Radarr's « is available » (minimum availability reached)
    added_at: datetime | None = None
    releases: Mapping[str, datetime] = field(default_factory=dict)  # cinema, digital, physical, air
    files: int = 0
    expected: int = 0  # episodes (series) or 1 (film)
    size: int | None = None
    quality: str | None = None
    link: str | None = None  # the title's page in the manager
    history: tuple[AcquisitionEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class FoundRelease:
    title: str
    indexer: str | None
    size: int | None
    quality: str | None
    seeders: int | None
    approved: bool
    rejections: tuple[str, ...] = ()


@runtime_checkable
class Acquisition(Protocol):
    async def status(self, kind: str, ids: Mapping[str, str]) -> SourceAcquisition | None:
        """``None`` when this manager does not follow the title."""
        ...

    async def search(self, kind: str, ids: Mapping[str, str]) -> Sequence[FoundRelease]:
        """An interactive search on the indexers — slow: called on demand only."""
        ...


@dataclass(frozen=True, slots=True)
class TorrentState:
    """027: a transfer as the torrent client sees it (matched to a download manager's queue by hash)."""

    download_id: str  # lower-case info hash
    name: str
    state: str  # downloading | stalled | queued | paused | checking | seeding | error | metadata
    progress: float
    download_speed: int = 0  # bytes/s
    upload_speed: int = 0
    eta_s: int | None = None
    seeds: int | None = None
    peers: int | None = None
    client: str = ""


@runtime_checkable
class DownloadClient(Protocol):
    async def torrents(self, hashes: Sequence[str]) -> Sequence[TorrentState]: ...


@runtime_checkable
class ItemLinks(Protocol):
    async def item_path(self, external_id: str, kind: str) -> str | None:
        """The path (and fragment) of a title's page in the service, joined to its public address — or a
        whole ``https://`` address when the service has a universal one (Plex's web app)."""
        ...


@dataclass(frozen=True, slots=True)
class MetadataPerson:
    name: str
    role: str | None = None  # character or job
    department: str = "cast"  # cast, directing, writing, production…
    image: str | None = None  # opaque ref served by the provider
    ids: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MetadataRecord:
    """What a metadata provider knows about one film, series or book (027)."""

    ids: Mapping[str, str]
    title: str
    original_title: str | None = None
    tagline: str | None = None
    overview: str | None = None
    genres: Sequence[str] = ()
    release_date: str | None = None  # ISO date
    runtime_min: int | None = None
    countries: Sequence[str] = ()
    languages: Sequence[str] = ()
    studios: Sequence[str] = ()
    budget: int | None = None
    revenue: int | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    status: str | None = None
    certification: str | None = None
    collection: Mapping[str, Any] | None = None  # {id, name, poster}
    seasons: int | None = None
    episodes: int | None = None
    networks: Sequence[str] = ()
    poster: str | None = None
    backdrop: str | None = None
    people: Sequence[MetadataPerson] = ()
    keywords: Sequence[str] = ()
    # 027: other artwork, swiped through at the top of the title's page
    backdrops: Sequence[str] = ()
    posters: Sequence[str] = ()


@runtime_checkable
class MetadataProvider(Protocol):
    async def lookup(
        self, kind: str, ids: Mapping[str, str], title: str, year: int | None, language: str
    ) -> MetadataRecord | None: ...

    async def fetch_image(self, ref: str, size: str) -> bytes: ...


# --- 027 (#2): the portal's player ---------------------------------------------------------------------
# The qualities a member picks, as Plex offers them: ``original`` streams the file as it is whenever the
# browser can (the video copied, at most the audio converted); the others cap the bitrate and the size.
QUALITIES: dict[str, tuple[int, int, int] | None] = {  # key → (max kbps, width, height)
    "original": None,
    "20m": (20_000, 1920, 1080),
    "12m": (12_000, 1920, 1080),
    "10m": (10_000, 1920, 1080),
    "8m": (8_000, 1920, 1080),
    "4m": (4_000, 1280, 720),
    "3m": (3_000, 1280, 720),
    "2m": (2_000, 1280, 720),
    "1500k": (1_500, 854, 480),
    "720k": (720, 640, 360),
    "320k": (320, 426, 240),
}


@dataclass(frozen=True, slots=True)
class StreamTrack:
    """An audio or subtitle track of one version of a title."""

    id: str
    kind: str  # audio | subtitle
    label: str
    language: str | None = None
    codec: str | None = None
    channels: int | None = None
    default: bool = False
    forced: bool = False
    selected: bool = False  # the member's current choice on the service
    text: bool = True  # a subtitle drawn as text by the player; image formats (PGS, VobSub) are burnt in
    external: bool = False  # a sidecar file next to the video


@dataclass(frozen=True, slots=True)
class StreamVersion:
    """One copy of a title (a 4K and a 1080p file of one film, say), with its tracks."""

    index: int
    label: str
    resolution: str | None = None  # 4k | 1080p | 720p | sd
    width: int | None = None
    height: int | None = None
    bitrate_kbps: int | None = None
    container: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    hdr: bool = False
    size: int | None = None
    audio: tuple[StreamTrack, ...] = ()
    subtitles: tuple[StreamTrack, ...] = ()
    previews: str | None = None  # the service's seek-bar previews of this file, an opaque ref (``image``)


@dataclass(frozen=True, slots=True)
class StreamMarker:
    """A stretch of the title: ``intro`` and ``credits`` (skippable), or a ``chapter`` with its name."""

    kind: str
    start_s: float
    end_s: float
    label: str | None = None
    image: str | None = None  # a chapter's picture, an opaque ref read through the channel's ``image``


@dataclass(frozen=True, slots=True)
class PlayableItem:
    """What the player needs to know of a title before playing it, as the member's account sees it."""

    external_id: str
    kind: str  # movie | episode
    title: str
    duration_s: float | None = None
    resume_s: float = 0.0  # where the member stopped last time (0 = from the start)
    watched: bool = False
    parent_title: str | None = None  # the series of an episode
    label: str | None = None  # « S02E05 »
    year: int | None = None
    versions: tuple[StreamVersion, ...] = ()
    markers: tuple[StreamMarker, ...] = ()
    chapters: tuple[StreamMarker, ...] = ()
    previous_id: str | None = None  # the episodes around this one
    next_id: str | None = None
    next_label: str | None = None
    image: str | None = None  # opaque ref served by ``media.library``'s ``fetch_image``


@dataclass(frozen=True, slots=True)
class ResumePoint:
    """027 (#23): a title the member is in the middle of on the service — or, without a position, the next
    episode of a series they follow (the service's own « Continue watching »)."""

    external_id: str
    kind: str  # movie | episode
    title: str
    parent_title: str | None = None  # the series of an episode
    label: str | None = None  # « S02E05 »
    position_s: float = 0.0  # 0: up next, not started
    series_id: str | None = None  # an episode's series on the service (its poster, its page)
    duration_s: float | None = None
    at: datetime | None = None  # when the member last watched
    ids: Mapping[str, str] = field(default_factory=dict)
    year: int | None = None


@dataclass(frozen=True, slots=True)
class StreamOptions:
    version: int = 0
    quality: str = "original"  # a key of QUALITIES
    audio: str | None = None  # a track id, or the member's current choice
    subtitle: str | None = None  # a track id, or ``None`` for none
    burn: bool = False  # burn the subtitle into the picture (always so for image formats)
    subtitle_size: int = 100  # percent, for burnt subtitles
    boost: int = 100  # audio boost, percent (Plex: 100 to 300)


@dataclass(frozen=True, slots=True)
class StreamStart:
    """A started stream: its media playlist (relative to the session), and what the service decided."""

    session: str
    playlist: str  # e.g. ``session/<id>/base/index.m3u8``
    video: str  # direct | copy | transcode
    audio: str  # copy | transcode
    subtitles: str  # none | text | burn
    width: int | None = None
    height: int | None = None
    bitrate_kbps: int | None = None
    video_codec: str | None = None
    audio_codec: str | None = None


@dataclass(frozen=True, slots=True)
class StreamBody:
    """An answer of the service streamed through the portal (a playlist or a segment)."""

    status: int
    content_type: str
    length: int | None
    chunks: AsyncIterator[bytes]


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    start_s: float
    end_s: float
    text: str


@runtime_checkable
class StreamChannel(Protocol):
    """One member's line to the service: every call is made as their account on it."""

    async def playable(self, external_id: str) -> PlayableItem: ...

    async def start(self, external_id: str, options: StreamOptions, session: str) -> StreamStart: ...

    def open(self, session: str, path: str) -> AbstractAsyncContextManager[StreamBody]:
        """A playlist or segment of a started stream (``path`` relative to the transcoder)."""
        ...

    def subtitles(
        self, external_id: str, options: StreamOptions, session: str
    ) -> AbstractAsyncContextManager[AsyncIterator[SubtitleCue]]:
        """The selected text subtitle as the transcoder reaches it, from where the stream stands."""
        ...

    async def report(
        self, external_id: str, session: str, state: str, position_s: float, duration_s: float | None
    ) -> None:
        """Where the member is (``playing``, ``paused``, ``stopped``): resume point, « watched », and the
        service's own activity (Tautulli sees the play)."""
        ...

    async def stop(self, session: str) -> None: ...

    async def image(self, ref: str, at_s: float | None = None) -> bytes:
        """A chapter's picture, or the preview of ``previews`` at ``at_s`` (JPEG)."""
        ...

    async def reset(self, external_id: str) -> None:
        """Forget where the member stopped (no resume point), keeping « watched » as it was."""
        ...

    async def continuing(self, limit: int) -> Sequence[ResumePoint]:
        """The member's « Continue watching » on the service, most recent first."""
        ...


@runtime_checkable
class MediaStreaming(Protocol):
    def channel(self, external_user_id: str | None) -> StreamChannel:
        """The channel of one account on the service (``None``: the service's own account)."""
        ...


DIGEST = "media.digest"


@dataclass(frozen=True, slots=True)
class DigestItem:
    """One title of a newsletter (027): what came out, arrived or comes next in the library."""

    title: str
    kind: str  # movie | series | book | audiobook | game | album
    date: str  # ISO day
    route: str  # portal route (``/media/<id>`` or ``/media/insights``)
    detail: str | None = None  # « S02E05 », a release type…


@runtime_checkable
class MediaDigest(Protocol):
    """027: the library's news for newsletters, read by the portal's own media module."""

    async def releases(self, since: date, until: date, limit: int) -> list[DigestItem]: ...

    async def additions(self, since: datetime, limit: int) -> list[DigestItem]: ...

    async def upcoming(self, until: date, limit: int) -> list[DigestItem]: ...


def _spec(name: str, protocol: type[Any], description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=True, description=description
    )


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(LIBRARY, MediaLibrary, "Media library of one service (sync records + images)"),
    _spec(PLAYBACK, MediaPlayback, "Live playback sessions and recent history of one service"),
    _spec(REQUESTS, RequestService, "Media requests on one request service"),
    _spec(ACCOUNTS, ServiceAccounts, "User accounts of one service, to match with portal members (027)"),
    _spec(ACTIVITY_HISTORY, ActivityHistory, "Full play/read history of one service, paged (027)"),
    _spec(CALENDAR, ReleaseCalendar, "Upcoming releases announced by one service (027)"),
    _spec(METADATA, MetadataProvider, "Metadata provider enriching the catalog (027)"),
    _spec(DOWNLOADS, DownloadQueue, "What a download manager is fetching or importing now (027)"),
    _spec(ACQUISITION, Acquisition, "Where a download manager stands on one title, and its search (027)"),
    _spec(DOWNLOAD_CLIENTS, DownloadClient, "Transfers of a torrent client, by hash (027)"),
    _spec(ITEM_LINKS, ItemLinks, "Where a title opens in its service (027)"),
    _spec(STREAMING, MediaStreaming, "Play a title in the portal, transcoded by its service (027)"),
    _spec(
        DIGEST, MediaDigest, "The library's releases, additions and upcoming titles, for newsletters (027)"
    ),
)
