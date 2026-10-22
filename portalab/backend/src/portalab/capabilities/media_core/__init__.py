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

    async def image(self, ref: str, size: str) -> bytes:
        """A metadata image's bytes (a person's portrait: what a face is compared with)."""
        ...

    async def role_images(self, person_ref: str) -> Sequence[CardImage] | None:
        """The images ``tmdb:<id>`` is tagged in, from the provider that knows them (``None``: none can)."""
        ...


SPECS: tuple[CapabilitySpec, ...] = (
    _spec(CATALOG, MediaCatalog, False, "Media catalog lookups (024)"),
    _spec(HISTORY, MediaHistoryReader, False, "Privacy-bounded media history and progress (024)"),
    _spec(QUOTA, RequestQuotaService, False, "Media request quota and extra units (024)"),
    _spec(RECOMMENDATIONS, RecommendationProvider, True, "Media recommendations (024 baseline, 018 later)"),
    _spec(RESCUES, RescueCredits, False, "Rescues saving a title from the cleanup's deletion (#57)"),
    _spec(RADIO_CREDITS, RadioCredits, False, "Requests to the radio's DJ bought in the shop (issue 184)"),
    _spec(CARD_SOURCES, CardSources, False, "The works present and their credits, for the cards (issue 229)"),
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
