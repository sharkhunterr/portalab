"""Issue 356: the month's media bingo, the media's side — the squares this library can fill (enough titles of
a genre, an era, a country…), and which ones each member ticked between two moments, each by the first title
that did it. Nothing to declare: what the services tell (plays, readings, game sessions) and the portal's own
reviews. A film or an episode counts watched to its end. An episode stands for its series (its genres, its
year, its country).

Issue 497: every kind of media weighs on the card — reading (books, audiobooks, comics, a book's genre),
playing (any game, a console, a game's genre), live TV and the radio — and only what members can really do:
a reading, playing or listening square is offered when someone used that kind on the portal lately; reading
and playing add up over the month (retro sessions are short), live TV and the radio half an hour too."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.media_core import BingoCell, BingoTick
from portalab.core.db import Database
from portalab.modules.media.models import (
    Activity,
    MediaObject,
    ObjectMetadata,
    ObjectTag,
    Review,
    TasteVerdict,
)
from portalab.modules.media.providers.insight_widgets import posters

FINISHED = 0.9
READ_S = 15 * 60  # a book read, an audiobook heard: a quarter of an hour over the month
PLAYED_S = 10 * 60  # games: ten minutes over the month (retro sessions last a few minutes)
TIMED_S = 30 * 60  # live TV, the radio: half an hour over the month
LATELY_DAYS = 90  # a reading, playing or listening square: someone used that kind on the portal lately
MAX_PLATFORMS = 8  # the consoles the library holds the most games of
ENOUGH = 5  # the titles of a genre, an era or a country the library holds for its square
LONG_S = 150 * 60
SHORT_S = 90 * 60
MARATHON = 3  # episodes of one series

# a genre as the services name it, in French or in English (the metadata provider's, the library's)
GENRES: dict[str, frozenset[str]] = {
    "comedy": frozenset({"comédie", "comedy", "humour", "humor"}),
    "drama": frozenset({"drame", "drama"}),
    "action": frozenset({"action"}),
    "horror": frozenset({"horreur", "horror"}),
    "scifi": frozenset({"science-fiction", "science fiction", "sf", "science-fiction et fantasy"}),
    "animation": frozenset({"animation"}),
    "thriller": frozenset({"thriller", "mystery thriller"}),
    "crime": frozenset({"crime", "policier"}),
    "romance": frozenset({"romance"}),
    "fantasy": frozenset({"fantastique", "fantasy"}),
    "mystery": frozenset({"mystère", "mystery"}),
    "family": frozenset({"familial", "family"}),
    "war": frozenset({"guerre", "war"}),
    "history": frozenset({"histoire", "history"}),
    "documentary": frozenset({"documentaire", "documentary"}),
    "music": frozenset({"musique", "music", "musical"}),
    "adventure": frozenset({"aventure", "adventure"}),
    "western": frozenset({"western"}),
}
COMICS = frozenset(
    {
        "comics",
        "comic book",
        "bande dessinée",
        "bd",
        "graphic novels",
        "graphic novels comics",
        "manga",
        "shonen manga",
        "comics manga",
    }
)
ERAS: dict[str, tuple[int, int]] = {
    "before1970": (0, 1969),
    "1970": (1970, 1979),
    "1980": (1980, 1989),
    "1990": (1990, 1999),
    "2000": (2000, 2009),
}
# issue 497: a book's genre (books and audiobooks), as the library names it
BOOK_GENRES: dict[str, frozenset[str]] = {
    "fantasy": frozenset({"fantasy", "fantastique", "science-fiction et fantasy"}),
    "scifi": frozenset({"science fiction", "science-fiction", "sf", "science-fiction et fantasy"}),
    "mystery": frozenset({"mystery", "thriller", "policier", "polar", "crime", "roman policier", "mystère"}),
    "adventure": frozenset({"adventure", "aventure"}),
    "humor": frozenset({"humor", "humour"}),
    "youth": frozenset({"childrens", "children", "jeunesse", "young adult", "juvenile fiction"}),
    "classics": frozenset({"classics", "classiques", "classique"}),
    "history": frozenset({"historical fiction", "history", "histoire", "roman historique"}),
    "romance": frozenset({"romance"}),
}
# issue 497: a game's genre — RomM's and its metadata providers' names (« shoot'em up / vertical »…)
GAME_GENRES: dict[str, frozenset[str]] = {
    "platform": frozenset({"platform", "platformer", "plateforme"}),
    "shooter": frozenset({"shooter", "shoot'em up", "shoot 'em up"}),
    "puzzle": frozenset({"puzzle", "thinking", "réflexion"}),
    "sport": frozenset({"sport", "sports"}),
    "racing": frozenset({"racing", "racing, driving", "course"}),
    "fighting": frozenset({"fighting", "beat'em up", "hack and slash/beat 'em up", "combat"}),
    "rpg": frozenset({"role-playing (rpg)", "role playing game", "rpg"}),
    "strategy": frozenset({"strategy", "turn-based strategy (tbs)", "tactical", "stratégie"}),
    "adventure": frozenset({"adventure", "aventure"}),
    "board": frozenset({"casino", "card & board game", "board game", "mahjong"}),
}


def _matches(values: set[str], names: frozenset[str]) -> bool:
    """A genre of the library matches a family when named as one of its names, or a kind of it
    (« shoot'em up / vertical », « sports / football »)."""
    return any(value in names or value.split(" /")[0] in names for value in values)


COUNTRIES = ("FR", "GB", "JP", "IT", "ES", "DE", "KR", "BE")
WATCHED = ("movie", "series")


@dataclass(frozen=True, slots=True)
class _Work:
    kind: str
    title: str
    year: int | None
    duration_s: float | None
    platform: str | None = None


def _platform(effective: object) -> str | None:
    value = effective.get("platform") if isinstance(effective, dict) else None
    return value if isinstance(value, str) and value else None


def _duration(effective: object) -> float | None:
    value = effective.get("duration_s") if isinstance(effective, dict) else None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def cells(database: Database, *, year: int, lately: datetime | None = None) -> list[BingoCell]:
    """Every square this library can fill: ``year`` is the month's (« a title out this year or last »);
    ``lately``: since when a kind must have been used on the portal for its reading, playing or listening
    squares (issue 497; ``None``: ever)."""
    out: list[BingoCell] = []
    async with database.session() as session:
        genres: dict[str, int] = defaultdict(int)
        for value, count in await session.execute(
            select(func.lower(ObjectTag.value), func.count(func.distinct(ObjectTag.object_id)))
            .join(MediaObject, MediaObject.id == ObjectTag.object_id)
            .where(
                ObjectTag.tag_kind == "genre", MediaObject.kind.in_(WATCHED), MediaObject.status == "active"
            )
            .group_by(func.lower(ObjectTag.value))
        ):
            genres[value] += int(count)
        out += [
            BingoCell(f"genre:{key}", "genre")
            for key, names in GENRES.items()
            if sum(genres.get(name, 0) for name in names) >= ENOUGH
        ]
        movies = MediaObject.kind == "movie", MediaObject.status == "active"
        for era, (low, high) in ERAS.items():
            count = await session.scalar(
                select(func.count()).where(*movies, MediaObject.year.between(low, high))
            )
            if (count or 0) >= ENOUGH:
                out.append(BingoCell(f"era:{era}", "era"))
        if (
            (await session.scalar(select(func.count()).where(*movies, MediaObject.year >= year - 1))) or 0
        ) >= ENOUGH:
            out.append(BingoCell("era:recent", "era"))
        for code in COUNTRIES:
            count = await session.scalar(
                select(func.count(func.distinct(ObjectMetadata.object_id))).where(
                    ObjectMetadata.status == "found", ObjectMetadata.data["countries"].contains([code])
                )
            )
            if (count or 0) >= ENOUGH:
                out.append(BingoCell(f"country:{code}", "country"))
        length = MediaObject.effective["duration_s"].as_float()
        if ((await session.scalar(select(func.count()).where(*movies, length >= LONG_S))) or 0) >= ENOUGH:
            out.append(BingoCell("length:long", "length"))
        if ((await session.scalar(select(func.count()).where(*movies, length <= SHORT_S))) or 0) >= ENOUGH:
            out.append(BingoCell("length:short", "length"))
        kinds: dict[str, int] = {
            kind: int(count)
            for kind, count in await session.execute(
                select(MediaObject.kind, func.count())
                .where(MediaObject.status == "active")
                .group_by(MediaObject.kind)
            )
        }
        if kinds.get("series"):
            out += [BingoCell("series:pilot", "series"), BingoCell("series:marathon", "series")]
        recent = Activity.started_at >= lately if lately is not None else Activity.id.is_not(None)
        used = {
            str(kind)
            for (kind,) in await session.execute(
                select(Activity.kind).where(Activity.counted.is_(True), recent).group_by(Activity.kind)
            )
        }
        out += await _reading(session, kinds, used)
        out += await _playing(session, kinds, used)
        out += [BingoCell(f"kind:{kind}", "listen") for kind in ("live", "radio") if kind in used]
    return [*out, BingoCell("review", "community"), BingoCell("later", "community")]


async def _tagged(session: AsyncSession, kinds: tuple[str, ...]) -> dict[str, int]:
    """How many active titles of these kinds carry each genre (lower-cased)."""
    return {
        str(value): int(count)
        for value, count in await session.execute(
            select(func.lower(ObjectTag.value), func.count(func.distinct(ObjectTag.object_id)))
            .join(MediaObject, MediaObject.id == ObjectTag.object_id)
            .where(ObjectTag.tag_kind == "genre", MediaObject.kind.in_(kinds), MediaObject.status == "active")
            .group_by(func.lower(ObjectTag.value))
        )
    }


def _families(tags: dict[str, int], families: dict[str, frozenset[str]]) -> list[str]:
    """The families the library holds enough titles of."""
    return [
        key
        for key, names in families.items()
        if sum(count for value, count in tags.items() if _matches({value}, names)) >= ENOUGH
    ]


async def _reading(session: AsyncSession, kinds: dict[str, int], used: set[str]) -> list[BingoCell]:
    """Books, audiobooks, comics and a book's genre — when someone reads or listens on the portal lately."""
    read = [kind for kind in ("book", "audiobook") if kinds.get(kind) and kind in used]
    out = [BingoCell(f"kind:{kind}", "read") for kind in read]
    if not {"book", "audiobook"} & used:
        return out
    tags = await _tagged(session, ("book", "audiobook"))
    if "book" in used and sum(tags.get(name, 0) for name in COMICS) >= ENOUGH:
        out.append(BingoCell("kind:comics", "read"))
    out += [BingoCell(f"read:{key}", "read") for key in _families(tags, BOOK_GENRES)]
    return out


async def _playing(session: AsyncSession, kinds: dict[str, int], used: set[str]) -> list[BingoCell]:
    """Any game, a console the library holds many games of, a game's genre — when someone plays lately."""
    if not kinds.get("game") or "game" not in used:
        return []
    out = [BingoCell("kind:game", "play")]
    genres = _families(await _tagged(session, ("game",)), GAME_GENRES)
    out += [BingoCell(f"play:{key}", "play") for key in genres]
    platform = MediaObject.effective["platform"].astext
    consoles = await session.execute(
        select(platform, func.count())
        .where(MediaObject.kind == "game", MediaObject.status == "active", platform.is_not(None))
        .group_by(platform)
        .having(func.count() >= ENOUGH)
        .order_by(func.count().desc(), platform)
        .limit(MAX_PLATFORMS)
    )
    out += [BingoCell(f"platform:{name}", "play") for name, _ in consoles if name]
    return out


async def ticks(
    database: Database, keys: Sequence[str], since: datetime, until: datetime, *, user: UUID | None = None
) -> dict[UUID, dict[str, BingoTick]]:
    """Per member, the squares among ``keys`` ticked between two moments, by the first title to tick each."""
    wanted = set(keys)
    async with database.session() as session:
        query = (
            select(Activity)
            .where(
                Activity.user_id.is_not(None),
                Activity.counted.is_(True),
                Activity.started_at >= since,
                Activity.started_at < until,
            )
            .order_by(Activity.started_at)
        )
        plays = list(
            (await session.execute(query.where(Activity.user_id == user) if user else query)).scalars()
        )
        ids = {p.work_id or p.object_id for p in plays} - {None}
        reviews = select(Review).where(Review.created_at >= since, Review.created_at < until)
        written = (
            list(
                (await session.execute(reviews.where(Review.user_id == user) if user else reviews)).scalars()
            )
            if "review" in wanted
            else []
        )
        ids |= {r.object_id for r in written}
        works = {
            row.id: _Work(row.kind, row.title, row.year, _duration(row.effective), _platform(row.effective))
            for row in (await session.execute(select(MediaObject).where(MediaObject.id.in_(ids)))).scalars()
        }
        genres: dict[UUID, set[str]] = defaultdict(set)
        for object_id, value in await session.execute(
            select(ObjectTag.object_id, func.lower(ObjectTag.value)).where(
                ObjectTag.tag_kind == "genre", ObjectTag.object_id.in_(ids)
            )
        ):
            genres[object_id].add(value)
        countries: dict[UUID, set[str]] = defaultdict(set)
        for object_id, found in await session.execute(
            select(ObjectMetadata.object_id, ObjectMetadata.data["countries"]).where(
                ObjectMetadata.object_id.in_(ids), ObjectMetadata.status == "found"
            )
        ):
            countries[object_id] |= {str(c) for c in found or [] if isinstance(c, str)}
        episodes = {p.object_id for p in plays if p.kind == "episode" and p.object_id}
        season = MediaObject.__table__.alias("season")
        pilots = {
            episode
            for episode, position, season_position in await session.execute(
                select(MediaObject.id, MediaObject.position, season.c.position)
                .join(season, season.c.id == MediaObject.parent_id)
                .where(MediaObject.id.in_(episodes))
            )
            if position == 1 and season_position == 1
        }
        later = (
            set(
                (
                    await session.execute(
                        select(TasteVerdict.user_id, TasteVerdict.object_id).where(
                            TasteVerdict.verdict == "later", TasteVerdict.object_id.in_(ids)
                        )
                    )
                ).all()
            )
            if "later" in wanted
            else set()
        )
    images = {work: UUID(image) for work, image in (await posters(database, works)).items()}
    out: dict[UUID, dict[str, BingoTick]] = defaultdict(dict)
    timed: dict[tuple[UUID, str], float] = defaultdict(float)
    marathon: dict[tuple[UUID, UUID], int] = defaultdict(int)

    def tick(member: UUID, key: str, work: UUID | None, title: str, at: datetime) -> None:
        if key in wanted and key not in out[member]:
            out[member][key] = BingoTick(work, title, images.get(work) if work else None, at)

    for play in plays:
        member = play.user_id
        assert member is not None
        work_id = play.work_id or play.object_id
        work = works.get(work_id) if work_id else None
        title = work.title if work else play.title
        at = play.started_at
        if play.kind in ("live", "radio"):
            timed[(member, play.kind)] += play.watched_s
            if timed[(member, play.kind)] >= TIMED_S:
                tick(member, f"kind:{play.kind}", None, play.title, at)
            continue
        if play.kind in ("book", "audiobook", "game"):
            # issue 497: reading and playing add up over the month, square by square
            tagged = genres[work_id] if work_id else set()
            if play.kind == "game":
                keys = ["kind:game"]
                keys += [f"play:{k}" for k, names in GAME_GENRES.items() if _matches(tagged, names)]
                if work and work.platform:
                    keys.append(f"platform:{work.platform}")
                enough = PLAYED_S
            else:
                keys = [f"kind:{play.kind}"]
                keys += [f"read:{k}" for k, names in BOOK_GENRES.items() if tagged & names]
                if play.kind == "book" and tagged & COMICS:
                    keys.append("kind:comics")
                enough = READ_S
            for key in keys:
                if key in wanted:
                    timed[(member, key)] += play.watched_s
                    if timed[(member, key)] >= enough:
                        tick(member, key, work_id, title, at)
            continue
        if play.kind not in ("movie", "episode") or (play.progress or 0.0) < FINISHED or work_id is None:
            continue
        for key, names in GENRES.items():
            if genres[work_id] & names:
                tick(member, f"genre:{key}", work_id, title, at)
        year = work.year if work else play.year
        if year is not None:
            for era, (low, high) in ERAS.items():
                if low <= year <= high:
                    tick(member, f"era:{era}", work_id, title, at)
            if year >= since.year - 1:
                tick(member, "era:recent", work_id, title, at)
        for code in countries[work_id]:
            tick(member, f"country:{code}", work_id, title, at)
        if play.kind == "movie":
            length = play.duration_s or (work.duration_s if work else None)
            if length is not None and length >= LONG_S:
                tick(member, "length:long", work_id, title, at)
            if length is not None and length <= SHORT_S:
                tick(member, "length:short", work_id, title, at)
        else:
            if play.object_id in pilots:
                tick(member, "series:pilot", work_id, title, at)
            marathon[(member, work_id)] += 1
            if marathon[(member, work_id)] >= MARATHON:
                tick(member, "series:marathon", work_id, title, at)
        if (member, work_id) in later:
            tick(member, "later", work_id, title, at)
    for review in written:
        found = works.get(review.object_id)
        tick(review.user_id, "review", review.object_id, found.title if found else "", review.created_at)
    return {member: dict(found) for member, found in out.items() if found}
