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
* ``media.metadata`` (027): a metadata provider (TMDB…) enriching catalog objects — backdrop, cast,
  collection, budget, revenue, genres… — and serving its images.

Providers are bound to one service (``instance_ref`` = the service id) and are usually wrapped by the 001
isolation guard, so calls may return a :class:`~portalab.capabilities.results.CapabilityResult`;
:func:`unwrap` turns that into a value or :class:`SourceUnavailable`. No provider-specific code lives in
the core: a Plex, Jellyfin or Sonarr connector only maps its API onto these shapes.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
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


class RequestPayload(BaseModel):
    """Payload of a ``request.service`` sync record (``external_id`` = the source request id)."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=500)
    kind: str = Field(min_length=1, max_length=40)
    ids: dict[str, str] = Field(default_factory=dict)
    state: RequestState = "pending"
    source_state: str = Field(default="", max_length=60)
    requester: str | None = Field(default=None, max_length=200)  # external user id on the service


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


@dataclass(frozen=True, slots=True)
class ActivityPage:
    items: Sequence[SourceActivity]
    cursor: str | None = None  # pass it back for the next page; ``None`` when exhausted


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


@runtime_checkable
class MetadataProvider(Protocol):
    async def lookup(
        self, kind: str, ids: Mapping[str, str], title: str, year: int | None, language: str
    ) -> MetadataRecord | None: ...

    async def fetch_image(self, ref: str, size: str) -> bytes: ...


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
)
