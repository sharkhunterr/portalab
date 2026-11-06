"""What Media (024) offers other modules (contracts/media-contracts.md): the media-type and detail-block
registries (owner-tagged, so a plugin's contributions disappear with it), and the read ports
``media.catalog``, ``media.history``, ``media.request_quota`` (Media owns quotas; Marketplace 015 only
credits/debits extra units — never ordering or priority) and ``media.recommendations``."""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

CATALOG = "media.catalog"
HISTORY = "media.history"
QUOTA = "media.request_quota"
RECOMMENDATIONS = "media.recommendations"
RESCUES = "media.rescues"  # #57: rescues bought in the shop, spent saving a title from deletion
RADIO_CREDITS = "media.radio_credits"  # issue 184: requests to the radio's DJ bought in the shop
CARD_SOURCES = "media.card_sources"  # issue 229: the works present, what the cards are made of
CONTENT_BOOSTERS = "media.content_boosters"  # issue 234: a content's booster, given by a reward rule
GAME_SOURCES = "media.game_sources"  # issue 265: what the games page draws from beyond the works
TECHNICAL_SHEETS = "media.technical_sheets"  # #354: a title's technical sheet, for the team on a ticket
CARD_FACES = "cards.faces"  # issue 265: a member's cards, as the memory game lays them face down


_KIND = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?")


class MediaRegistryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MediaType:
    kind: str
    label_key: str
    owner: str
    parent_kinds: tuple[str, ...] = ()
    finished_threshold: float | None = 0.9  # share of the duration; None = only an explicit ending counts
    playable: bool = True


class MediaTypeRegistry:
    def __init__(self) -> None:
        self._types: dict[str, MediaType] = {}

    def register(self, media_type: MediaType) -> MediaType:
        if not _KIND.fullmatch(media_type.kind):
            raise MediaRegistryError(f"invalid media kind {media_type.kind!r}")
        if media_type.owner.startswith("plugin:") and not media_type.kind.startswith(
            media_type.owner.split(":", 1)[1] + "."
        ):
            raise MediaRegistryError("plugin media kinds are namespaced '<plugin>.<kind>'")
        existing = self._types.get(media_type.kind)
        if existing is not None and existing.owner != media_type.owner:
            raise MediaRegistryError(f"media kind {media_type.kind!r} belongs to {existing.owner}")
        threshold = media_type.finished_threshold
        if threshold is not None and not 0 < threshold <= 1:
            raise MediaRegistryError("finished_threshold is a share in (0, 1]")
        self._types[media_type.kind] = media_type
        return media_type

    def get(self, kind: str) -> MediaType | None:
        return self._types.get(kind)

    def all(self) -> list[MediaType]:
        return [self._types[k] for k in sorted(self._types)]

    def unregister(self, owner: str) -> int:
        doomed = [k for k, t in self._types.items() if t.owner == owner]
        for key in doomed:
            del self._types[key]
        return len(doomed)


BASELINE: tuple[tuple[str, tuple[str, ...], float | None], ...] = (
    ("movie", (), 0.9),
    ("series", (), None),
    ("season", ("series",), None),
    ("episode", ("season", "series"), 0.9),
    ("book", (), 0.95),
    ("audiobook", (), 0.95),
    ("game", (), None),
    ("album", (), None),
    ("track", ("album",), 0.8),
)

default_media_types = MediaTypeRegistry()


def register_media_type(
    kind: str,
    label_key: str,
    *,
    owner: str,
    parent_kinds: Sequence[str] = (),
    finished_threshold: float | None = 0.9,
    playable: bool = True,
    registry: MediaTypeRegistry = default_media_types,
) -> MediaType:
    return registry.register(
        MediaType(kind, label_key, owner, tuple(parent_kinds), finished_threshold, playable)
    )


def register_baseline(registry: MediaTypeRegistry, owner: str = "module:media") -> None:
    for kind, parents, threshold in BASELINE:
        if registry.get(kind) is None:
            register_media_type(
                kind,
                f"media:kind.{kind}",
                owner=owner,
                parent_kinds=parents,
                finished_threshold=threshold,
                playable=kind not in ("series", "season", "album"),
                registry=registry,
            )


# --- detail-page blocks (declarative, permission-gated) ---------------------------------------------------
@dataclass(frozen=True, slots=True)
class DetailBlock:
    key: str  # ``<owner-key>.<name>``
    owner: str
    title_key: str
    template: Literal["facts", "list", "text", "links"]
    load: Callable[[UUID, Principal], Any] = field(compare=False)  # async → Mapping (template data)
    required_permission: str | None = None
    kinds: tuple[str, ...] = ()  # empty = every kind
    order: int = 100


class DetailBlockRegistry:
    def __init__(self) -> None:
        self._blocks: dict[str, DetailBlock] = {}

    def register(self, block: DetailBlock) -> DetailBlock:
        existing = self._blocks.get(block.key)
        if existing is not None and existing.owner != block.owner:
            raise MediaRegistryError(f"detail block {block.key!r} belongs to {existing.owner}")
        self._blocks[block.key] = block
        return block

    def for_kind(self, kind: str) -> list[DetailBlock]:
        blocks = [b for b in self._blocks.values() if not b.kinds or kind in b.kinds]
        return sorted(blocks, key=lambda b: (b.order, b.key))

    def unregister(self, owner: str) -> int:
        doomed = [k for k, b in self._blocks.items() if b.owner == owner]
        for key in doomed:
            del self._blocks[key]
        return len(doomed)


default_detail_blocks = DetailBlockRegistry()


def register_detail_block(block: DetailBlock, registry: DetailBlockRegistry = default_detail_blocks) -> None:
    registry.register(block)


# --- read ports ---------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class MediaSummary:
    id: UUID
    kind: str
    title: str
    year: int | None
    available: bool
    route: str
    genres: tuple[str, ...] = ()
    # issue 261: for an episode, its series' title, its season's number and its own
    series: str | None = None
    season: int | None = None
    number: int | None = None


@dataclass(frozen=True, slots=True)
class HistoryItem:
    object_id: UUID
    kind: str
    title: str
    occurred_at: datetime
    completed: bool
    position_s: float


@dataclass(frozen=True, slots=True)
class Progress:
    object_id: UUID
    percent: float
    resume_position_s: float
    state: Literal["in_progress", "finished"]
    last_occurred_at: datetime


@runtime_checkable
class MediaCatalog(Protocol):
    async def get(self, object_id: UUID, viewer: Principal) -> MediaSummary | None: ...

    async def resolve_ref(self, ref: str, viewer: Principal) -> MediaSummary | None:
        """``media:<uuid>`` or ``<scheme>:<value>`` (strong external id); ``None`` if unknown or hidden."""
        ...


@runtime_checkable
class MediaHistoryReader(Protocol):
    async def for_user(
        self, user: UUID, viewer: Principal, *, limit: int = 50, kind: str | None = None
    ) -> Sequence[HistoryItem]: ...

    async def progress(self, user: UUID, viewer: Principal, object_id: UUID) -> Progress | None: ...


@runtime_checkable
class RequestQuotaService(Protocol):
    async def available(self, user: UUID) -> Mapping[str, int]: ...

    async def add_units(self, user: UUID, units: int, source_ref: str, idempotency_key: str) -> int: ...

    async def remove_units(self, user: UUID, units: int, source_ref: str, idempotency_key: str) -> int: ...


@runtime_checkable
class RescueCredits(Protocol):
    """#57: Media keeps the rescues; Marketplace only credits those it sold (idempotent per purchase)."""

    async def grant(self, user: UUID, count: int, source_ref: str) -> int:
        """Credit ``count`` rescues; the new balance."""
        ...


@runtime_checkable
class RadioCredits(Protocol):
    """Issue 184: Media keeps the radio request credits; Marketplace credits those it sold (once each)."""

    async def grant(self, user: UUID, count: int, source_ref: str) -> int:
        """Credit ``count`` requests; the new balance."""
        ...


@runtime_checkable
class RecommendationProvider(Protocol):
    async def recommend(self, viewer: Principal, *, limit: int) -> Sequence[UUID]: ...


def _spec(name: str, protocol: type[Any], multi: bool, description: str) -> CapabilitySpec:
    return CapabilitySpec(
        name=name, version="1.0", protocol=protocol, multi_provider=multi, description=description
    )


@dataclass(frozen=True, slots=True)
class CardPerson:
    """Issue 229: someone credited on a work — ``order``: their place in the credits (0: the first)."""

    ref: str  # ``tmdb:<id>`` when the provider knows them, else ``name:<name>``
    name: str
    category: str  # cast, director, creator, writer, composer
    role: str | None  # a character or a job
    order: int
    image: str | None  # a metadata image's reference (``/media/metadata-images``)


@dataclass(frozen=True, slots=True)
class CardWork:
    """Issue 229: a film or a series present in the catalog, with what its cards need."""

    object_id: UUID
    kind: str
    title: str
    year: int | None
    countries: Sequence[str]
    languages: Sequence[str]
    vote_count: int
    vote_average: float | None
    tagline: str | None
    poster: str | None
    backdrop: str | None
    backdrops: Sequence[str]
    collection: Mapping[str, Any] | None
    people: Sequence[CardPerson]
    updated_at: datetime
    available: bool
    tmdb: str | None = None  # the work's TMDB id (its characters' images are tagged with it)
    ids: Mapping[str, str] = field(default_factory=dict)  # every id known (tvdb: a series' on art sites)
    genres: Sequence[str] = ()
    # issue 229: the work's own figures, printed on its cards (frozen when its set is made): budget, revenue,
    # runtime (minutes), seasons, its director's name
    facts: Mapping[str, Any] = field(default_factory=dict)
    overview: str | None = None  # issue 265: what it tells (the games' synopsis to guess from)
    keywords: Sequence[str] = ()  # issue 296: the metadata's keywords (a theme booster's: kaiju, samurai…)


@dataclass(frozen=True, slots=True)
class CardImage:
    """Issue 229: an image a person is tagged in — the work it comes from (its TMDB id), its kind (a still, a
    backdrop, a poster), its shape and how liked it is."""

    work: str
    image: str
    image_type: str
    aspect: float
    votes: float


@runtime_checkable
class CardSources(Protocol):
    """Issue 229: what the media catalog offers the cards — every work with metadata (or those changed since
    ``since``), and the work a played object belongs to (an episode: its series)."""

    async def works(self, *, since: datetime | None = None) -> Sequence[CardWork]: ...

    async def present(self) -> Sequence[UUID]: ...

    async def work_of(self, object_id: UUID) -> UUID | None: ...

    async def season_of(self, object_id: UUID) -> int | None:
        """Issue 234: a season's number (``None``: not a season)."""
        ...

    async def image(self, ref: str, size: str) -> bytes:
        """A metadata image's bytes (a person's portrait: what a face is compared with)."""
        ...

    async def role_images(self, person_ref: str) -> Sequence[CardImage] | None:
        """The images ``tmdb:<id>`` is tagged in, from the provider that knows them (``None``: none can)."""
        ...

    async def frames(self, object_id: UUID, at: Sequence[float]) -> Sequence[bytes] | None:
        """Issue 230: still images of a work's own video at those moments (fractions of its length), from a
        media server that holds it (``None``: none can)."""
        ...


@runtime_checkable
class ContentBoosters(Protocol):
    """Issue 234: ``count`` boosters of a content (a film, a season: its work's cards) given to a member —
    once per member and content, whatever asks; ``0`` when given already, or the content has no cards."""

    async def give(self, user: UUID, object_id: UUID, count: int, reason: str) -> int: ...

    async def give_among(self, user: UUID, among: Mapping[str, Any], count: int, reason: str) -> int:
        """Issue 356: ``count`` boosters of the works an event names rather than one content — a ``genre``
        (the bingo's words: ``scifi``, ``comedy``…), a release ``year`` (its edition), the whole library when
        it names neither or nothing is drawable there; once per ``reason``."""
        ...


@dataclass(frozen=True, slots=True)
class PlayableGame:
    """Issue 265: a title of the library a week's challenge is about — a game (RomM), a film, a book, an
    audiobook."""

    object_id: UUID
    title: str
    platform: str | None
    image_id: UUID | None
    year: int | None = None
    kind: str = "game"


@dataclass(frozen=True, slots=True)
class SeenWork:
    """Issue 265: a work a member watched, read or played (a series for its episodes), the last time."""

    object_id: UUID
    kind: str
    title: str
    year: int | None
    last_at: datetime


@runtime_checkable
class TechnicalSheets(Protocol):
    """#354: what the team needs to answer a report on a title — each media server's files and streams (video,
    audio tracks, subtitles) and when it was added there, and its download manager's side (the release
    grabbed, its indexer, the download client and the torrent's hash, its quality and size)."""

    async def sheet(self, viewer: Principal, object_id: UUID) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class BingoCell:
    """Issue 356: a square a month's media bingo may hold — its ``key`` (``genre:horror``, ``era:1980``,
    ``country:JP``, ``kind:audiobook``, ``review``…) and its ``group`` (genre, era, country, length, series,
    kind, community), the library having what it takes to tick it."""

    key: str
    group: str


@dataclass(frozen=True, slots=True)
class BingoTick:
    """Issue 356: what ticked a square for a member — the work (``object_id`` None for live TV or the radio),
    its title and poster, and when."""

    object_id: UUID | None
    title: str
    image_id: UUID | None
    at: datetime


@runtime_checkable
class GameSources(Protocol):
    """Issue 265: what the games page needs of the media beyond the works the cards are made of — a series'
    theme music (the blind test), the library's titles a week's challenge is about, and how far each member
    went in one since a moment (what its services tell: play sessions, history, the portal's progress)."""

    async def theme(self, object_id: UUID) -> bytes | None: ...

    async def blurred(self, ref: str, radius: int) -> bytes:
        """A metadata image (a scene of a work) blurred by ``radius`` pixels (0: sharp), as a JPEG."""
        ...

    async def titles(self, kind: str, *, limit: int) -> Sequence[PlayableGame]:
        """Titles of a kind present in the library, at random (a game of a franchise first)."""
        ...

    async def title(self, object_id: UUID) -> PlayableGame | None: ...

    async def progress(self, kind: str, object_id: UUID, since: datetime) -> Mapping[UUID, float]:
        """Per member since ``since``: a game's seconds played; a film's, a book's, an audiobook's furthest
        point (0 to 1) — what their services and the portal's player and reader tell."""
        ...

    async def seen(self, user: UUID, *, limit: int) -> Sequence[SeenWork]:
        """The works a member watched, read or played, the latest first (what their services tell)."""
        ...

    async def bingo_cells(self, *, year: int) -> Sequence[BingoCell]:
        """Issue 356: every square this library can fill (enough titles of the genre, the era, the country…);
        ``year`` is the month's (« a title out this year or last »)."""
        ...

    async def bingo_ticks(
        self, keys: Sequence[str], since: datetime, until: datetime, *, user: UUID | None = None
    ) -> Mapping[UUID, Mapping[str, BingoTick]]:
        """Issue 356: per member (or one), the squares among ``keys`` ticked between two moments, each by the
        first title that did it (what their services tell: plays, readings, game sessions, reviews)."""
        ...


@runtime_checkable
class CardFaces(Protocol):
    """Issue 265: ``count`` of a member's own cards (the rarest first, then any other), each as the cards'
    page shows it — the memory game's faces; fewer when there are not so many."""

    async def faces(self, user: UUID, count: int) -> Sequence[Mapping[str, Any]]: ...


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(CATALOG, MediaCatalog, False, "Media catalog lookups (024)"),
    _spec(HISTORY, MediaHistoryReader, False, "Privacy-bounded media history and progress (024)"),
    _spec(QUOTA, RequestQuotaService, False, "Media request quota and extra units (024)"),
    _spec(RECOMMENDATIONS, RecommendationProvider, True, "Media recommendations (024 baseline, 018 later)"),
    _spec(RESCUES, RescueCredits, False, "Rescues saving a title from the cleanup's deletion (#57)"),
    _spec(RADIO_CREDITS, RadioCredits, False, "Requests to the radio's DJ bought in the shop (issue 184)"),
    _spec(CARD_SOURCES, CardSources, False, "The works present and their credits, for the cards (issue 229)"),
    _spec(CONTENT_BOOSTERS, ContentBoosters, False, "A content's booster given to a member (issue 234)"),
    _spec(GAME_SOURCES, GameSources, False, "Theme music, games and play time for the games page (265)"),
    _spec(TECHNICAL_SHEETS, TechnicalSheets, False, "A title's technical sheet for the team (#354)"),
    _spec(CARD_FACES, CardFaces, False, "A member's cards, as the memory game lays them (issue 265)"),
)

QuotaSummary = Mapping[str, int]
__all__ = [
    "BASELINE",
    "CATALOG",
    "HISTORY",
    "QUOTA",
    "RADIO_CREDITS",
    "RECOMMENDATIONS",
    "RESCUES",
    "SPECS",
    "DetailBlock",
    "DetailBlockRegistry",
    "HistoryItem",
    "MediaCatalog",
    "MediaHistoryReader",
    "MediaRegistryError",
    "MediaSummary",
    "MediaType",
    "MediaTypeRegistry",
    "Progress",
    "QuotaSummary",
    "RadioCredits",
    "RecommendationProvider",
    "RequestQuotaService",
    "RescueCredits",
    "default_detail_blocks",
    "default_media_types",
    "register_baseline",
    "register_detail_block",
    "register_media_type",
]
