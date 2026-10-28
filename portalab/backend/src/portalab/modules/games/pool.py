"""Issue 265: what the games draw from — the films and series of the library that a metadata provider knows
(the works the cards are made of: their poster, cast, synopsis, year, rating), kept a while in memory; the
posters blurred on the server (the page never holds the sharp image before the answer); the series' theme
music (the blind test), a few kept at hand."""

import re
import unicodedata
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from portalab.capabilities.media_core import CARD_SOURCES, GAME_SOURCES, CardWork
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.errors import Unavailable
from portalab.core.time import Clock, utc_now
from portalab.modules.games.settings import GamesConfig

REFRESH = timedelta(minutes=30)
# how blurred a scene is, step after step (its time runs: each step a fifth of the round)
BLUR = (60, 36, 22, 12, 5, 0)


class NoTitles(Unavailable):
    default_code = "games.no_titles"
    default_title = "Not enough titles to play"


@dataclass(frozen=True, slots=True)
class Person:
    name: str
    role: str | None
    image: str | None


@dataclass(frozen=True, slots=True)
class Item:
    id: UUID
    kind: str
    title: str
    year: int | None
    rating: float | None
    votes: int
    poster: str | None
    scenes: tuple[str, ...]  # its backdrops: images of the work without its title
    overview: str | None
    tagline: str | None
    genres: tuple[str, ...]
    cast: tuple[Person, ...]
    runtime: int | None
    available: bool


def fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in plain if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^0-9a-z]+", " ", plain).split())


def _item(work: CardWork) -> Item:
    cast = tuple(
        Person(p.name, p.role, p.image)
        for p in sorted(work.people, key=lambda p: p.order)
        if p.category == "cast"
    )
    runtime = work.facts.get("runtime_min") if work.facts else None
    return Item(
        id=work.object_id,
        kind=work.kind,
        title=work.title,
        year=work.year,
        rating=work.vote_average,
        votes=work.vote_count,
        poster=work.poster,
        # its scenes without words first (TMDB ranks them so): the title must not be written on it
        scenes=tuple(work.backdrops[:3]) or ((work.backdrop,) if work.backdrop else ()),
        overview=work.overview,
        tagline=work.tagline,
        genres=tuple(work.genres),
        cast=cast,
        runtime=int(runtime) if isinstance(runtime, int) else None,
        available=work.available,
    )


class Pool:
    def __init__(self, capabilities: CapabilityRegistry, *, clock: Clock | None = None) -> None:
        self.capabilities = capabilities
        self.clock = clock
        self._items: list[Item] = []
        self._loaded: datetime | None = None
        self._images: OrderedDict[tuple[str, int], bytes] = OrderedDict()
        self._themes: OrderedDict[UUID, bytes | None] = OrderedDict()

    def _provider(self, name: str) -> object:
        providers = self.capabilities.system_providers(name)
        if not providers:
            raise Unavailable("The library cannot be read.", code="games.no_library")
        return providers[0].provider

    async def all(self) -> list[Item]:
        now = utc_now(self.clock)
        if self._loaded is None or now - self._loaded > REFRESH:
            works = await self._provider(CARD_SOURCES).works()  # type: ignore[attr-defined]
            self._items = [_item(w) for w in works]
            self._loaded = now
        return self._items

    async def items(self, config: GamesConfig) -> list[Item]:
        """The titles the games may ask about: the kinds set, voted enough to be known, present."""
        library = config.library
        return [
            i
            for i in await self.all()
            if i.kind in library.kinds
            and i.votes >= library.min_votes
            and (i.available or not library.available_only)
        ]

    async def blurred(self, ref: str, step: int) -> bytes:
        """A poster at a step of its blur (the last one sharp), blurred by the media, kept a while."""
        step = max(0, min(step, len(BLUR) - 1))
        key = (ref, step)
        if key in self._images:
            self._images.move_to_end(key)
            return self._images[key]
        data: bytes = await self._provider(GAME_SOURCES).blurred(ref, BLUR[step])  # type: ignore[attr-defined]
        self._images[key] = data
        while len(self._images) > 120:
            self._images.popitem(last=False)
        return data

    async def theme(self, object_id: UUID) -> bytes | None:
        if object_id in self._themes:
            self._themes.move_to_end(object_id)
            return self._themes[object_id]
        sources = self.capabilities.system_providers(GAME_SOURCES)
        found: bytes | None = await sources[0].provider.theme(object_id) if sources else None
        self._themes[object_id] = found
        while len(self._themes) > 40:
            self._themes.popitem(last=False)
        return found

    async def with_themes(self, candidates: Sequence[Item], wanted: int) -> list[Item]:
        """Series whose theme music their media server keeps, up to ``wanted`` (a few asked at most)."""
        out: list[Item] = []
        for item in candidates[: wanted * 4]:
            if await self.theme(item.id):
                out.append(item)
                if len(out) >= wanted:
                    break
        return out
