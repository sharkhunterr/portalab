"""Issue 190: what each work of the library is made of, for the taste — its genres, keywords, saga, its
people (director, first roles, writers, authors, narrators), studios, publisher, platform and countries —
read in one go and kept a while (the library changes slowly). A trait is a pair ``(kind, key)``: the key is
folded (no case, no accents) so that the same author or genre from two sources is one trait."""

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import Float, Integer, cast, select

from portalab.modules.media.models import Credit, MediaObject, ObjectMetadata, ObjectTag

Trait = tuple[str, str]

# what a member's taste is told by, in each family of works
FAMILY = {"movie": "video", "series": "video", "book": "books", "audiobook": "books", "game": "games"}
KINDS = tuple(FAMILY)
# how much a shared trait says of two works: a saga or an author much more than a country
WEIGHTS = {
    "saga": 2.5,
    "franchise": 1.5,
    "author": 2.2,
    "director": 1.6,
    "creator": 1.4,
    "cast": 1.0,
    "narrator": 1.0,
    "writer": 0.8,
    "genre": 1.0,
    "platform": 0.6,
    "keyword": 0.5,
    "studio": 0.5,
    "publisher": 0.4,
    "country": 0.3,
}
CAST_ROLES = 6  # the first roles only: an actor billed twentieth says little of a film
KEYWORDS = 15
# the same genre told in two languages by two sources (the books' are often English, the films' French)
GENRES = {
    "adventure": "aventure",
    "fantasy": "fantastique",
    "sci fi": "science fiction",
    "sf": "science fiction",
    "horror": "horreur",
    "comedy": "comedie",
    "drama": "drame",
    "mystery": "mystere",
    "history": "histoire",
    "historical": "histoire",
    "war": "guerre",
    "documentary": "documentaire",
    "family": "familial",
    "kids": "familial",
    "music": "musique",
    "sports": "sport",
    "role playing game": "role playing rpg",
}
# what a library files a work under that says nothing of what it is (Grimmory's shelves, formats)
NOT_GENRES = {
    "accueil",
    "home",
    "none",
    "audiobook",
    "audiobooks",
    "ebooks",
    "ebook",
    "livres audio",
    "fiction",
}
# what a keyword or a saga says of how a work was made or sold, not of what it is
STOP = {
    ("keyword", "sequel"),
    ("keyword", "duringcreditsstinger"),
    ("keyword", "aftercreditsstinger"),
    ("keyword", "based on novel or book"),
    ("keyword", "based on comic"),
    ("keyword", "based on manga"),
    ("keyword", "remake"),
    ("keyword", "woman director"),
    ("keyword", "live action remake"),
    ("saga", "audible original"),
    ("franchise", "audible original"),
}
_SAGA = re.compile(
    r"\s*[-\u2013(]?\s*\b(saga|collection|la saga|trilogie|trilogy)\b\s*\)?\s*$", re.IGNORECASE
)
# what a ROM's name says when it is no game of the catalogue: « ZZZ(notgame) », « (Hack) », « (Pirate) »,
# a file name left as it was (« Star Trek (…).bin »)
_NOT_A_GAME = re.compile(
    r"^zzz|\([^)]*\b(?:notgame|pirate|hack|bootleg|unl|proto|beta|demo)\b[^)]*\)"
    r"|\.(?:nes|sfc|smc|gbc?|gba|n64|z64|v64|nds|md|gen|sms|gg|pce|a26|lnx|bin|iso|cue|chd|zip|7z)$",
    re.IGNORECASE,
)
PRIOR = 6.6  # the rating a title is assumed to have before its votes tell otherwise
VOTES = 40


def fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in plain if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^0-9a-z]+", " ", plain).split())


def genres_of(value: str) -> list[str]:
    """« Science-Fiction & Fantastique » and « Science-fiction et fantasy » are two genres; « Sci-Fi » and
    « Science-Fiction » one; a library's shelf (« Accueil ») or a format (« Ebooks ») none."""
    out = []
    for part in re.split(r"\s*&\s*|\s*/\s*|,\s*|\s+(?:et|and)\s+", value):
        key = fold(part)
        if key and key not in NOT_GENRES:
            out.append(GENRES.get(key, key))
    return out


def saga_key(name: str) -> str:
    """« Mission : Impossible - Saga » and the book series « Mission Impossible » are one franchise."""
    return fold(_SAGA.sub("", name))


@dataclass(slots=True)
class Work:
    id: UUID
    kind: str
    title: str
    year: int | None
    available: bool
    quality: float  # a rating out of 10, shrunk towards PRIOR while it has few votes
    votes: int
    traits: set[Trait] = field(default_factory=set)

    @property
    def family(self) -> str:
        return FAMILY[self.kind]


@dataclass(slots=True)
class Index:
    works: dict[UUID, Work]
    labels: dict[Trait, str]  # a trait's name as shown (« Christopher Nolan », « Science-Fiction »)
    df: dict[str, Counter[Trait]]  # per family: how many works have each trait
    sizes: Counter[str]  # per family: how many works there are

    def share(self, family: str, trait: Trait) -> float:
        """How common a trait is in a family's works (« Drame » often, a director seldom)."""
        return max(1, self.df.get(family, Counter()).get(trait, 0)) / max(1, self.sizes[family])


def _quality(average: Any, votes: Any) -> tuple[float, int]:
    try:
        rating = float(average) if average is not None else None
    except (TypeError, ValueError):
        rating = None
    count = int(votes) if isinstance(votes, int | float) else 0
    if rating is None or rating <= 0:
        return PRIOR - 0.2, 0
    if count <= 0:  # a book's readers' rating, its count unknown: half believed
        return (rating + PRIOR) / 2, 0
    return (rating * count + PRIOR * VOTES) / (count + VOTES), count


async def build_index(session: Any) -> Index:
    works: dict[UUID, Work] = {}
    labels: dict[Trait, str] = {}

    def add(work: Work, kind: str, name: str, key: str | None = None) -> None:
        key = key if key is not None else fold(name)
        if not key:
            return
        trait = (kind, key)
        if trait in STOP:
            return
        work.traits.add(trait)
        labels.setdefault(trait, name.strip())

    platforms: dict[UUID, str] = {}
    sagas: set[str] = set()
    rows = await session.execute(
        select(
            MediaObject.id,
            MediaObject.kind,
            MediaObject.title,
            MediaObject.year,
            MediaObject.available,
            MediaObject.effective["rating"],
            MediaObject.effective["series"].astext,
            MediaObject.effective["publisher"].astext,
            MediaObject.effective["platform"].astext,
        ).where(
            MediaObject.status == "active",
            MediaObject.parent_id.is_(None),
            MediaObject.kind.in_(KINDS),
        )
    )
    for object_id, kind, title, year, available, rating, series, publisher, platform in rows:
        if kind == "game" and _NOT_A_GAME.search(title):
            continue  # a dump's demo, hack or pirate cartridge, an unnamed file: never a game to offer
        quality, votes = _quality(rating, 0)
        work = Work(object_id, kind, title, year, bool(available), quality, votes)
        works[object_id] = work
        if series and kind in ("book", "audiobook", "game"):  # a book's series, a game's franchise: its saga
            add(work, "saga", series)
            sagas.add(saga_key(series))
            add(work, "franchise", series, saga_key(series))
        if publisher:
            add(work, "publisher", publisher)
        if platform:
            platforms[object_id] = fold(platform)
            add(work, "platform", platform)
    for object_id, value in await session.execute(
        select(ObjectTag.object_id, ObjectTag.value).where(ObjectTag.tag_kind == "genre")
    ):
        tagged = works.get(object_id)
        if tagged is None or fold(value) == platforms.get(object_id):  # a game's console is not a genre
            continue
        for key in genres_of(value):
            add(tagged, "genre", value, key)
    # a library's own tags: a book's themes, a game's franchises and modes (RomM, from IGDB)
    tags: dict[UUID, list[str]] = defaultdict(list)
    for object_id, value in await session.execute(
        select(ObjectTag.object_id, ObjectTag.value).where(ObjectTag.tag_kind == "tag")
    ):
        if object_id in works:
            tags[object_id].append(value)
            add(works[object_id], "keyword", value)
    for object_id, role, name, folded, position in await session.execute(
        select(Credit.object_id, Credit.role, Credit.name, Credit.folded, Credit.position).where(
            Credit.role.in_(("director", "creator", "cast", "writer", "author", "narrator"))
        )
    ):
        credited = works.get(object_id)
        if (
            credited is None
            or (role == "cast" and position >= CAST_ROLES)
            or (role == "writer" and position >= 3)
            or (role == "director" and credited.kind == "series")  # a series' directors are its episodes'
        ):
            continue
        add(credited, role, name, fold(folded or name))
    for object_id, keywords, saga, studios, countries, average, votes in await session.execute(
        select(
            ObjectMetadata.object_id,
            ObjectMetadata.data["keywords"],
            ObjectMetadata.data["collection"],
            ObjectMetadata.data["studios"],
            ObjectMetadata.data["countries"],
            cast(ObjectMetadata.data["vote_average"].astext, Float),
            cast(ObjectMetadata.data["vote_count"].astext, Integer),
        ).where(ObjectMetadata.status == "found")
    ):
        described = works.get(object_id)
        if described is None:
            continue
        described.quality, described.votes = _quality(average, votes)
        for keyword in (keywords if isinstance(keywords, list) else [])[:KEYWORDS]:
            if isinstance(keyword, str):
                add(described, "keyword", keyword)
        if isinstance(saga, dict) and saga.get("name"):
            name = str(saga["name"])
            add(described, "saga", _SAGA.sub("", name) or name, f"tmdb:{saga.get('id') or fold(name)}")
            sagas.add(saga_key(name))
            add(described, "franchise", _SAGA.sub("", name) or name, saga_key(name))
        for studio in (studios if isinstance(studios, list) else [])[:3]:
            if isinstance(studio, str):
                add(described, "studio", studio)
        for country in (countries if isinstance(countries, list) else [])[:2]:
            if isinstance(country, str):
                add(described, "country", country, country.upper())
    # a title named after a saga known elsewhere (« Star Wars : The Clone Wars », a game « Star Wars : … »),
    # or a game of a franchise (IGDB's « Alien ») joins it, whatever its medium
    for object_id, values in tags.items():
        for value in values:
            key = saga_key(value)
            if key in sagas:
                add(works[object_id], "franchise", value, key)
    for work in works.values():
        for head in re.split(r"\s*[:\u2013]\s*|\s+-\s+", work.title)[:1]:
            key = fold(head)
            if key in sagas and ("franchise", key) not in work.traits:
                add(work, "franchise", head, key)
    df: dict[str, Counter[Trait]] = {}
    sizes: Counter[str] = Counter()
    for work in works.values():
        df.setdefault(work.family, Counter()).update(work.traits)
        sizes[work.family] += 1
    return Index(works, labels, df, sizes)
