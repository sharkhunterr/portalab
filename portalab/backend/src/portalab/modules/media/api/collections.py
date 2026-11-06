"""Issue 361: the collections of the library — a film's saga (TMDB's « collection »), a book's or an
audiobook's series, a game's franchise — told the same way on every title's page, and their own page.

``GET /media/{object_id}/collection``: the collection a title belongs to, with its other titles in the
library, in order (no service asked: what the library knows). ``GET /media/collection?ref=…``: the whole
collection — ``tmdb:<id>`` a saga, ``series:<name>`` a series or a franchise —, and for a saga every film
TMDB knows of it, each told available, asked for or missing (then where to ask for it); issue 362: for a
book series every volume a book database knows (Hardcover), each in the library or absent. The reference is
a query parameter: a series' name may hold a slash."""

import logging
from collections import Counter
from functools import partial
from typing import Annotated, Any, Literal
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select

from portalab.capabilities.media import (
    BOOK_SERIES,
    GAME_DATABASE,
    METADATA,
    BookDetails,
    BookSeries,
    GameDetails,
    GameFranchise,
    unwrap,
)
from portalab.capabilities.media_core import WantedTitle
from portalab.core.errors import NotFound, Unavailable
from portalab.modules.media.api.people import (
    BOOK_KINDS,
    FilmCreditOut,
    _bibliography,
    _filmography,
    _identify,
    _sheet_url,
)
from portalab.modules.media.api.router import MediaCard, Module, Reader, _asked, _card
from portalab.modules.media.databases import TIMEOUT as DATABASE_TIMEOUT
from portalab.modules.media.library_match import MediaLibraryMatch
from portalab.modules.media.matching import fold
from portalab.modules.media.models import ExternalId, MediaObject, ObjectMetadata
from portalab.modules.media.permissions import MEDIA_REQUEST
from portalab.modules.media.providers.insight_widgets import posters

router = APIRouter(prefix="/api/v1", tags=["media"])
log = logging.getLogger(__name__)
LIMIT = 500
SAGA = "tmdb:"
SERIES = "series:"


class CollectionItemOut(MediaCard):
    position: float | None = None  # its volume in a series
    platform: str | None = None  # a game's: the same game may be there for several


class CollectionOut(BaseModel):
    ref: str  # ``tmdb:<id>`` (a film saga) or ``series:<name>`` (a book series, a game franchise)
    source: Literal["saga", "series"]
    name: str
    poster: str | None = None  # a saga's own poster, the provider's image (``/media/metadata-images``)
    items: list[CollectionItemOut]  # its titles in the library, in order
    parts: list[FilmCreditOut] = []  # its page: every film of a saga, every volume of a book series
    askable: bool = False  # the member may ask for the films missing


class CollectionNotFound(NotFound):
    default_code = "media.collection_not_found"
    default_title = "No such collection in the library"


def _position(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _order(row: MediaObject) -> tuple[Any, ...]:
    position = _position(row.effective.get("series_position"))
    return (position is None, position or 0, row.year is None, row.year or 0, row.sort_title, str(row.id))


async def _items(module: Module, rows: list[MediaObject]) -> list[CollectionItemOut]:
    rows = sorted(rows, key=_order)
    images = await posters(module.database, [row.id for row in rows])
    cards = await _asked(
        module, [_card(row, UUID(images[row.id]) if row.id in images else None) for row in rows]
    )
    return [
        CollectionItemOut(
            **card.model_dump(),
            position=_position(row.effective.get("series_position")),
            platform=str(row.effective["platform"])[:80] if row.effective.get("platform") else None,
        )
        for card, row in zip(cards, rows, strict=True)
    ]


async def _saga(module: Module, saga_id: str) -> tuple[str | None, str | None, list[MediaObject]]:
    """A saga's name and poster as the library's films tell them, and those films."""
    async with module.database.session() as session:
        found = (
            await session.execute(
                select(MediaObject, ObjectMetadata.data["collection"])
                .join(ObjectMetadata, ObjectMetadata.object_id == MediaObject.id)
                .where(
                    ObjectMetadata.status == "found",
                    ObjectMetadata.data["collection"]["id"].astext == saga_id,
                    MediaObject.status == "active",
                )
                .limit(LIMIT)
            )
        ).all()
    saga = next((c for _, c in found if isinstance(c, dict) and c.get("name")), None)
    return (
        str(saga["name"]) if saga else None,
        str(saga["poster"]) if saga and saga.get("poster") else None,
        [row for row, _ in found],
    )


async def _series(module: Module, name: str) -> tuple[str | None, list[MediaObject]]:
    """A series' (a franchise's) titles, whatever case they write its name in; its most common spelling."""
    async with module.database.session() as session:
        rows = list(
            (
                await session.execute(
                    select(MediaObject)
                    .where(
                        func.lower(MediaObject.effective["series"].astext) == name.strip().lower(),
                        MediaObject.status == "active",
                    )
                    .limit(LIMIT)
                )
            ).scalars()
        )
    spellings = Counter(str(row.effective["series"]) for row in rows)
    return (spellings.most_common(1)[0][0] if spellings else None), rows


async def _parts(module: Module, saga_id: str, language: str) -> list[FilmCreditOut] | None:
    """Every film of a saga as the metadata provider knows it (TMDB), with its standing in the library."""
    for registration in module.capabilities.system_providers(METADATA):
        saga = getattr(registration.provider, "saga", None)
        if saga is None:
            continue
        try:
            credits = unwrap(await saga(saga_id, language))
        except Exception as exc:
            log.info("saga lookup failed: %s: %s", type(exc).__name__, exc)
            return None  # the saga's page still shows the library's films
        if credits is None:
            return None
        parts = await _filmography(module, credits)
        parts.sort(key=lambda part: (part.year is None, part.year or 0, part.title))
        return parts
    return None


def _cover_url(service: str, ref: str | None) -> str | None:
    if not ref:
        return None
    return f"/api/v1/media/book-covers?{urlencode({'service': service, 'ref': ref})}"


async def _volumes(module: Module, name: str, rows: list[MediaObject]) -> list[FilmCreditOut]:
    """Issue 362: every volume of a book series as a book database knows it (Hardcover) — the series
    told apart from its namesakes by the library's own volumes, as it identified them —, each found in the
    library as identified, by its title or by its volume number."""
    books = [row for row in rows if row.kind in BOOK_KINDS]
    if not books:
        return []
    for registration in module.capabilities.system_providers(BOOK_SERIES):
        service = registration.instance_ref
        known, _ = await _identify(module, service, [row.id for row in books])
        try:
            found = unwrap(await registration.provider.series(name, sorted(known)))
        except Exception as exc:
            log.info("book series lookup failed: %s: %s", type(exc).__name__, exc)
            continue
        if not isinstance(found, BookSeries) or not found.volumes:
            continue
        parts = await _bibliography(
            module,
            found.volumes,
            works=[row.id for row in books],
            known=known,
            cover=partial(_cover_url, service),
            sheet=partial(_sheet_url, service),
        )
        # a volume the library has under another title and without its ISBN: by its number
        numbered = {_position(row.effective.get("series_position")): row for row in books}
        numbered.pop(None, None)
        images = await posters(module.database, [row.id for row in numbered.values()])
        for index, part in enumerate(parts):
            row = numbered.get(part.position) if part.status == "absent" else None
            if row is not None:
                parts[index] = part.model_copy(
                    update={
                        "title": row.title,
                        "kind": row.kind,  # #372: an audiobook told as one
                        "status": "available" if row.available else "unavailable",
                        "object_id": str(row.id),
                        "route": f"/media/{row.id}",
                        "image_id": images.get(row.id),
                    }
                )
        parts.sort(key=lambda part: (part.position is None, part.position or 0, part.year or 0))
        return parts
    return []


class BookEditionOut(BaseModel):
    title: str
    language: str | None = None
    format: str | None = None
    audio: bool = False
    ids: dict[str, list[str]] = {}
    publisher: str | None = None
    year: int | None = None
    cover: str | None = None  # through the portal (``/media/book-covers``)


class BookSeriesOut(BaseModel):
    name: str
    position: float | None = None
    route: str | None = None  # its page, when the library has some of its volumes


class BookSheetOut(BaseModel):
    """#367: a book the library may lack, as the book database tells it — and where the library has it
    (as a book, as an audiobook), found by one of its editions' identifiers or titles by its authors."""

    service: str
    ref: str
    title: str
    subtitle: str | None = None
    description: str | None = None
    year: int | None = None
    release_date: str | None = None
    pages: int | None = None
    cover: str | None = None
    authors: list[str] = []
    series: list[BookSeriesOut] = []
    genres: list[str] = []
    moods: list[str] = []
    rating: float | None = None  # out of 10, as a film's
    votes: int = 0
    readers: int = 0
    editions: list[BookEditionOut] = []
    library: dict[str, str] = {}  # kind (book, audiobook) → the library's title's id


async def _held(module: Module, book: BookDetails) -> dict[str, str]:
    """Where the library has the book: one of its editions' identifiers, else one of their titles by one of
    its authors — as a book and as an audiobook."""
    ids: dict[str, list[str]] = {}
    for edition in book.editions:
        for scheme, values in edition.ids.items():
            ids.setdefault(scheme, []).extend(values)
    titles = list(dict.fromkeys([book.title, *(e.title for e in book.editions)]))[:12]
    wanted = [
        WantedTitle(f"{kind}|{index}", kind, title, tuple(book.authors), ids if index == 0 else {})
        for kind in sorted(BOOK_KINDS)
        for index, title in enumerate(titles)
    ]
    found = await MediaLibraryMatch(module.database).find(wanted)
    out: dict[str, str] = {}
    for key in sorted(found, key=lambda k: int(k.split("|")[1])):
        out.setdefault(key.split("|")[0], str(found[key].object_id))
    return out


@router.get("/media/book", response_model=BookSheetOut)
async def book_sheet(
    _: Reader,
    module: Module,
    service: Annotated[str, Query(pattern=r"^[0-9a-f-]{36}$")],
    ref: Annotated[str, Query(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")],
) -> BookSheetOut:
    """#367: a book's sheet from the book database that knows it (Hardcover) — its description, authors,
    series, genres and editions —, and where the library has it."""
    provider = next(
        (r.provider for r in module.capabilities.system_providers(BOOK_SERIES) if r.instance_ref == service),
        None,
    )
    if provider is None:
        raise CollectionNotFound("No such book database.")
    try:
        book = unwrap(await provider.book(ref))
    except Exception as exc:
        raise Unavailable("The book cannot be told right now.", code="media.book_unavailable") from exc
    if not isinstance(book, BookDetails):
        raise CollectionNotFound(f"no book {ref[:40]!r}")
    series = []
    for name, position in book.series:
        found, rows = await _series(module, name)
        series.append(
            BookSeriesOut(
                name=name,
                position=position,
                route=f"/media/collection?{urlencode({'ref': f'{SERIES}{found}'})}" if rows else None,
            )
        )
    return BookSheetOut(
        service=service,
        ref=book.ref,
        title=book.title,
        subtitle=book.subtitle,
        description=book.description,
        year=book.year,
        release_date=book.release_date,
        pages=book.pages,
        cover=_cover_url(service, book.cover),
        authors=list(book.authors),
        series=series,
        genres=list(book.genres),
        moods=list(book.moods),
        rating=book.rating,
        votes=book.votes,
        readers=book.readers,
        editions=[
            BookEditionOut(
                title=e.title,
                language=e.language,
                format=e.format,
                audio=e.audio,
                ids={k: list(v) for k, v in e.ids.items()},
                publisher=e.publisher,
                year=e.year,
                cover=_cover_url(service, e.cover),
            )
            for e in book.editions
        ],
        library=await _held(module, book),
    )


def _game_image(service: str, ref: str | None, size: str = "cover") -> str | None:
    if not ref:
        return None
    return f"/api/v1/media/game-images?{urlencode({'service': service, 'ref': ref, 'size': size})}"


def _game_sheet(service: str, ref: str) -> str:
    return f"/media/game?{urlencode({'service': service, 'ref': ref})}"


async def _igdb_of(module: Module, ids: list[UUID]) -> dict[str, UUID]:
    """The library's games by the game database's ids they carry (RomM keeps IGDB's)."""
    async with module.database.session() as session:
        rows = await session.execute(
            select(ExternalId.value, ExternalId.object_id).where(
                ExternalId.object_id.in_(ids), ExternalId.scheme == "igdb"
            )
        )
        return {str(value): object_id for value, object_id in rows}


async def _games(module: Module, name: str, rows: list[MediaObject]) -> list[FilmCreditOut]:
    """#368: every game of a franchise as a game database knows it (IGDB) — the franchise told apart from
    its namesakes by the library's own games —, each found in the library by its id there, else by its
    title; the others absent, leading to their sheet."""
    games = [row for row in rows if row.kind == "game"]
    if not games:
        return []
    by_id = await _igdb_of(module, [row.id for row in games])
    rows_of = {row.id: row for row in games}
    by_title = {fold(row.title): row for row in games}
    for registration in module.capabilities.system_providers(GAME_DATABASE):
        service = registration.instance_ref
        try:
            found = unwrap(await registration.provider.franchise(name, sorted(by_id)))
        except Exception as exc:
            log.info("game franchise lookup failed: %s: %s", type(exc).__name__, exc)
            continue
        if not isinstance(found, GameFranchise) or not found.games:
            continue
        images = await posters(module.database, [row.id for row in games])
        parts: list[FilmCreditOut] = []
        claimed: set[UUID] = set()
        for game in found.games:
            object_id = by_id.get(game.tmdb_id)
            row = rows_of.get(object_id) if object_id else by_title.get(fold(game.title))
            if row is not None and row.id in claimed:
                row = None  # a library game is one of them only
            if row is not None:
                claimed.add(row.id)
            parts.append(
                FilmCreditOut(
                    tmdb_id=game.tmdb_id,
                    kind="game",
                    title=row.title if row else game.title,
                    year=game.year,
                    role=None,
                    department="game",
                    poster=None,
                    image_id=images.get(row.id) if row else None,
                    rating=game.vote_average,
                    votes=game.vote_count,
                    status=("available" if row.available else "unavailable") if row else "absent",
                    object_id=str(row.id) if row else None,
                    route=f"/media/{row.id}" if row else _game_sheet(service, game.tmdb_id),
                    cover=_game_image(service, game.poster),
                )
            )
        return parts
    return []


class GameSheetOut(BaseModel):
    """#368: a game the library may lack, as the game database tells it — and the library's title when it
    has it (by its id there, else its title)."""

    service: str
    ref: str
    title: str
    summary: str | None = None
    storyline: str | None = None
    year: int | None = None
    release_date: str | None = None
    cover: str | None = None
    backdrop: str | None = None  # its first artwork or screenshot
    images: list[str] = []  # its screenshots and artworks, ready URLs
    genres: list[str] = []
    themes: list[str] = []
    modes: list[str] = []
    platforms: list[str] = []
    developers: list[str] = []
    publishers: list[str] = []
    franchises: list[BookSeriesOut] = []  # each linked when the library has some of its games
    names: dict[str, str] = {}
    rating: float | None = None
    votes: int = 0
    trailer: str | None = None
    library: str | None = None  # the library's title's id


@router.get("/media/game", response_model=GameSheetOut)
async def game_sheet(
    _: Reader,
    module: Module,
    service: Annotated[str, Query(pattern=r"^[0-9a-f-]{36}$")],
    ref: Annotated[str, Query(min_length=1, max_length=20, pattern=r"^[0-9]+$")],
) -> GameSheetOut:
    """#368: a game's sheet from the game database that knows it (IGDB), and where the library has it."""
    provider = next(
        (
            r.provider
            for r in module.capabilities.system_providers(GAME_DATABASE)
            if r.instance_ref == service
        ),
        None,
    )
    if provider is None:
        raise CollectionNotFound("No such game database.")
    try:
        game = unwrap(await provider.game(ref))
    except Exception as exc:
        raise Unavailable("The game cannot be told right now.", code="media.game_unavailable") from exc
    if not isinstance(game, GameDetails):
        raise CollectionNotFound(f"no game {ref[:20]!r}")
    held = await MediaLibraryMatch(module.database).find(
        [WantedTitle("game", "game", game.title, (), {"igdb": [game.ref]})]
    )
    franchises = []
    for name in game.franchises:
        found, rows = await _series(module, name)
        franchises.append(
            BookSeriesOut(
                name=name,
                route=f"/media/collection?{urlencode({'ref': f'{SERIES}{found}'})}" if rows else None,
            )
        )
    images = [_game_image(service, ref_, "screenshot") for ref_ in game.images]
    return GameSheetOut(
        service=service,
        ref=game.ref,
        title=game.title,
        summary=game.summary,
        storyline=game.storyline,
        year=game.year,
        release_date=game.release_date,
        cover=_game_image(service, game.cover),
        backdrop=_game_image(service, game.images[0], "artwork") if game.images else None,
        images=[url for url in images if url],
        genres=list(game.genres),
        themes=list(game.themes),
        modes=list(game.modes),
        platforms=list(game.platforms),
        developers=list(game.developers),
        publishers=list(game.publishers),
        franchises=franchises,
        names=dict(game.names),
        rating=game.rating,
        votes=game.votes,
        trailer=game.trailer,
        library=str(held["game"].object_id) if "game" in held else None,
    )


class DatabaseTitleOut(BaseModel):
    """#375: a book or a game the library lacks, from the book or game database — opening its sheet."""

    kind: str
    title: str
    year: int | None = None
    creator: str | None = None  # its authors, its studio
    cover: str | None = None  # a ready URL, through the portal
    route: str  # its sheet


@router.get("/media/discover/titles", response_model=list[DatabaseTitleOut])
async def database_titles(
    principal: Reader, module: Module, q: Annotated[str, Query(min_length=2, max_length=200)]
) -> list[DatabaseTitleOut]:
    """#375: « Ask for a title » finds books and games too — those the library lacks, in the member's
    language (the request service's films and series are its own search)."""
    items = await module.database_titles.found(
        q, await module.member_language(principal), 20, budget=DATABASE_TIMEOUT
    )
    return [
        DatabaseTitleOut(
            kind=str(item.facets.get("type") or "book"),
            title=str(item.facets.get("name") or item.title),
            year=int(item.facets["year"]) if str(item.facets.get("year") or "").isdigit() else None,
            creator=item.facets.get("creator"),
            cover=item.facets.get("cover"),
            route=item.url_ref,
        )
        for item in items
    ]


@router.get("/media/game-images")
async def game_image(
    _: Reader,
    module: Module,
    service: Annotated[str, Query(pattern=r"^[0-9a-f-]{36}$")],
    ref: Annotated[str, Query(min_length=1, max_length=40, pattern=r"^[a-z0-9]+$")],
    size: Annotated[str, Query(pattern=r"^(cover|screenshot|artwork)$")] = "cover",
) -> Response:
    """#368: a game's cover, screenshot or artwork from the game database, through the portal."""
    provider = next(
        (
            r.provider
            for r in module.capabilities.system_providers(GAME_DATABASE)
            if r.instance_ref == service
        ),
        None,
    )
    if provider is None:
        raise CollectionNotFound("No such image.")
    try:
        data = unwrap(await provider.image(ref, size))
    except Exception as exc:
        raise Unavailable("The image cannot be fetched right now.", code="media.image_unavailable") from exc
    return Response(
        content=data,
        media_type=_image_type(data),
        headers={
            "Cache-Control": "private, max-age=2592000, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.get("/media/book-covers")
async def book_cover(
    _: Reader,
    module: Module,
    service: Annotated[str, Query(pattern=r"^[0-9a-f-]{36}$")],
    ref: Annotated[str, Query(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_./-]+$")],
) -> Response:
    """Issue 362: a volume's cover from the book database that has it, through the portal: browsers never
    call the services."""
    provider = next(
        (r.provider for r in module.capabilities.system_providers(BOOK_SERIES) if r.instance_ref == service),
        None,
    )
    if provider is None:
        raise CollectionNotFound("No such cover.")
    try:
        data = unwrap(await provider.cover(ref, "w185"))
    except Exception as exc:
        raise Unavailable("The cover cannot be fetched right now.", code="media.image_unavailable") from exc
    return Response(
        content=data,
        media_type=_image_type(data),
        headers={
            "Cache-Control": "private, max-age=2592000, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


def _image_type(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


@router.get("/media/{object_id}/collection", response_model=CollectionOut | None)
async def title_collection(_: Reader, module: Module, object_id: UUID) -> CollectionOut | None:
    async with module.database.session() as session:
        row = await session.get(MediaObject, object_id)
        meta = await session.get(ObjectMetadata, object_id)
    if row is None or row.status != "active":
        return None
    collection = meta.data.get("collection") if meta is not None and meta.status == "found" else None
    if isinstance(collection, dict) and collection.get("id"):
        saga_id = str(collection["id"])
        name, poster, rows = await _saga(module, saga_id)
        return CollectionOut(
            ref=f"{SAGA}{saga_id}",
            source="saga",
            name=name or str(collection.get("name") or ""),
            poster=poster,
            items=await _items(module, rows),
        )
    series = row.effective.get("series")
    if isinstance(series, str) and series.strip():
        name, rows = await _series(module, series)
        return CollectionOut(
            ref=f"{SERIES}{name or series}",
            source="series",
            name=name or series,
            items=await _items(module, rows),
        )
    return None


@router.get("/media/collection", response_model=CollectionOut)
async def collection(
    principal: Reader, module: Module, ref: Annotated[str, Query(min_length=2, max_length=260)]
) -> CollectionOut:
    if ref.startswith(SAGA) and ref.removeprefix(SAGA).isdigit():
        saga_id = ref.removeprefix(SAGA)
        name, poster, rows = await _saga(module, saga_id)
        parts = await _parts(module, saga_id, await module.member_language(principal))
        if not rows and not parts:
            raise CollectionNotFound(f"no saga {saga_id}")
        askable = module.requestable.configured() and await module.authorizer.is_allowed(
            principal, MEDIA_REQUEST
        )
        return CollectionOut(
            ref=ref,
            source="saga",
            name=name or "",
            poster=poster,
            items=await _items(module, rows),
            parts=parts or [],
            askable=askable,
        )
    if ref.startswith(SERIES) and ref.removeprefix(SERIES).strip():
        name, rows = await _series(module, ref.removeprefix(SERIES)[:200])
        if not rows or name is None:
            raise CollectionNotFound(f"no series {ref[:60]!r}")
        return CollectionOut(
            ref=f"{SERIES}{name}",
            source="series",
            name=name,
            items=await _items(module, rows),
            # a book series' volumes (issue 362), a game franchise's games (#368)
            parts=await _volumes(module, name, rows) or await _games(module, name, rows),
        )
    raise CollectionNotFound(f"no collection {ref[:60]!r}")
