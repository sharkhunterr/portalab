"""HTTP API of a person's page (#92): ``GET /media/person?name=…`` — an actor's, a director's, an author's,
a narrator's titles in the library, by role, with their portrait; and what the metadata provider (TMDB)
knows of them — biography, birth, what they are known for — with their whole filmography, each title told
available, asked for, not available or missing from the library (and then where to ask for it).
The name is a query parameter: a name may hold a slash (« AC/DC »)."""

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Literal
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel
from sqlalchemy import select

from portalab.capabilities.media import BOOK_SERIES, OwnedBook, PersonCredit, PersonRecord, unwrap
from portalab.core.errors import NotFound, Unavailable
from portalab.modules.media.api.router import MediaCard, Module, Reader, _asked, _card
from portalab.modules.media.matching import fold
from portalab.modules.media.models import ExternalId, MediaObject, MediaRequest
from portalab.modules.media.permissions import MEDIA_REQUEST
from portalab.modules.media.providers.insight_widgets import posters
from portalab.modules.media.requests.discovery import OPEN

router = APIRouter(prefix="/api/v1", tags=["media"])
log = logging.getLogger(__name__)
KNOWN_FOR = 10
BOOK_KINDS = ("book", "audiobook")
Status = Literal["available", "requested", "unavailable", "missing", "absent"]  # absent: a book not there


class PersonCreditOut(BaseModel):
    role: str
    items: list[MediaCard]


class PersonProfileOut(BaseModel):
    biography: str | None
    birthday: str | None
    deathday: str | None
    place_of_birth: str | None
    known_for: str | None
    popularity: float | None
    also_known_as: list[str]
    imdb: str | None


class FilmCreditOut(BaseModel):
    tmdb_id: str
    kind: str
    title: str
    year: int | None
    role: str | None
    department: str
    poster: str | None  # the provider's image (``/media/metadata-images``)
    image_id: str | None  # the library's poster, when it has the title
    rating: float | None
    votes: int
    status: Status
    object_id: str | None
    route: str | None  # its page in the library, else where to ask for it (when one can)
    cover: str | None = None  # issue 362: a book's cover from its book database, a ready URL (the portal's)
    position: float | None = None  # issue 362: its volume in a series


class PersonOut(BaseModel):
    name: str
    portrait: str | None  # a ready URL: the portal serves it (browsers never call the services)
    sources: list[str] = []  # the services that told about them
    roles: list[str]
    titles: int
    credits: list[PersonCreditOut]
    profile: PersonProfileOut | None = None
    known_for: list[FilmCreditOut] = []
    filmography: list[FilmCreditOut] = []
    counts: dict[str, int] = {}
    askable: bool = False  # the member may ask for the titles missing (a request service is there)


class PersonNotFound(NotFound):
    default_code = "media.person_not_found"
    default_title = "Nobody by that name in the library"


def _image(value: str | None) -> UUID | None:
    return UUID(value) if value else None


async def _filmography(module: Module, credits: Sequence[PersonCredit]) -> list[FilmCreditOut]:
    """Each title of the filmography with its standing in the library: available, asked for (a request in
    progress), there but not available, or missing (then its « ask for it » page, when one can ask)."""
    credits = [credit for credit in credits if credit.kind != "book"]  # the books: ``_bibliography``
    wanted = {credit.tmdb_id for credit in credits}
    known: dict[tuple[str, str], tuple[UUID, bool]] = {}
    asked: set[UUID] = set()
    if wanted:
        async with module.database.session() as session:
            rows = await session.execute(
                select(ExternalId.value, MediaObject.kind, MediaObject.id, MediaObject.available)
                .join(MediaObject, MediaObject.id == ExternalId.object_id)
                .where(
                    ExternalId.scheme == "tmdb",
                    ExternalId.value.in_(wanted),
                    MediaObject.kind.in_(("movie", "series")),
                    MediaObject.status == "active",
                )
            )
            for value, kind, object_id, available in rows:
                current = known.get((value, kind))
                if current is None or (available and not current[1]):
                    known[(value, kind)] = (object_id, bool(available))
            ids = [object_id for object_id, _ in known.values()]
            if ids:
                asked = {
                    object_id
                    for object_id in (
                        await session.execute(
                            select(MediaRequest.object_id).where(
                                MediaRequest.object_id.in_(ids), MediaRequest.state.in_(OPEN)
                            )
                        )
                    ).scalars()
                    if object_id is not None
                }
    images = await posters(module.database, [object_id for object_id, _ in known.values()])
    askable = module.requestable.configured()
    out = []
    for credit in credits:
        found = known.get((credit.tmdb_id, credit.kind))
        object_id = found[0] if found else None
        status: Status
        if found and found[1]:
            status = "available"
        elif object_id in asked:
            status = "requested"
        else:
            status = "unavailable" if object_id else "missing"
        if object_id:
            route: str | None = f"/media/{object_id}"
        else:
            route = f"/media/discover/{credit.kind}/{credit.tmdb_id}" if askable else None
        out.append(
            FilmCreditOut(
                tmdb_id=credit.tmdb_id,
                kind=credit.kind,
                title=credit.title,
                year=credit.year,
                role=credit.role,
                department=credit.department,
                poster=credit.poster,
                image_id=images.get(object_id) if object_id else None,
                rating=credit.vote_average,
                votes=credit.vote_count,
                status=status,
                object_id=str(object_id) if object_id else None,
                route=route,
            )
        )
    return out


def _cover_url(service: str | None, ref: str | None) -> str | None:
    if not service or not ref:
        return None
    return f"/api/v1/media/person/portrait?{urlencode({'service': service, 'ref': ref, 'size': 'w185'})}"


def _sheet_url(service: str | None, ref: str | None) -> str | None:
    """#367: the portal's sheet of a book the library lacks, as the book database tells it."""
    if not service or not ref:
        return None
    return f"/media/book?{urlencode({'service': service, 'ref': ref})}"


@dataclass(frozen=True, slots=True)
class _Owned:
    object_id: UUID
    available: bool
    title: str


async def _identify(
    module: Module, service: str | None, works: Sequence[UUID]
) -> tuple[dict[str, _Owned], list[list[PersonCredit]]]:
    """Issue 362: the library's books among ``works`` as the book database ``service`` knows them (by an
    edition's ISBN, its own id, an edition's title by the same author) — each of its books' ids with the
    library's book; and each library book's candidates, the likeliest first (a bibliography may list none
    of them: a translation's split part)."""
    provider = next(
        (r.provider for r in module.capabilities.system_providers(BOOK_SERIES) if r.instance_ref == service),
        None,
    )
    if provider is None or not works:
        return {}, []
    async with module.database.session() as session:
        rows = list(
            (
                await session.execute(
                    select(MediaObject).where(
                        MediaObject.id.in_(works),
                        MediaObject.kind.in_(BOOK_KINDS),
                        MediaObject.status == "active",
                    )
                )
            ).scalars()
        )
        ids: dict[UUID, dict[str, list[str]]] = {}
        for object_id, scheme, value in await session.execute(
            # every identifier the library holds: the book database reads those it knows
            select(ExternalId.object_id, ExternalId.scheme, ExternalId.value).where(
                ExternalId.object_id.in_([row.id for row in rows])
            )
        ):
            ids.setdefault(object_id, {}).setdefault(scheme, []).append(value)
    owned = [
        OwnedBook(
            key=str(row.id),
            title=row.title,
            authors=tuple(str(a) for a in (row.effective.get("authors") or [])[:10] if a),
            ids=ids.get(row.id, {}),
        )
        for row in rows
    ]
    try:
        found = unwrap(await provider.identify(owned))
    except Exception as exc:
        log.info("book identification failed: %s: %s", type(exc).__name__, exc)
        return {}, []
    known: dict[str, _Owned] = {}
    candidates: list[list[PersonCredit]] = []
    for row in rows:
        credits = list((found or {}).get(str(row.id)) or ())
        mine = _Owned(row.id, bool(row.available), row.title)
        for credit in credits:
            if credit.tmdb_id not in known or (mine.available and not known[credit.tmdb_id].available):
                known[credit.tmdb_id] = mine
        if credits:
            candidates.append(credits)
    return known, candidates


async def _bibliography(
    module: Module,
    credits: Sequence[PersonCredit],
    *,
    works: Sequence[UUID] = (),
    known: Mapping[str, _Owned] | None = None,
    cover: Callable[[str | None], str | None] = lambda _: None,
    sheet: Callable[[str | None], str | None] = lambda _: None,
) -> list[FilmCreditOut]:
    """Issue 362: each book of a bibliography (or a series) with its standing in the library — found as
    the book database identified the library's books (``known``, by the database's id), else by its title
    among ``works`` (the person's, the series' own titles): available, there but not available, or absent
    (no service asks for books), told by the library's title when there. Its cover: the library's, else the
    book database's (``cover`` turns its reference into a URL)."""
    books = [credit for credit in credits if credit.kind == "book"]
    if not books:
        return []
    known = known or {}
    by_title: dict[str, _Owned] = {}
    if works:
        async with module.database.session() as session:
            for object_id, title, available in await session.execute(
                select(MediaObject.id, MediaObject.title, MediaObject.available).where(
                    MediaObject.id.in_(works),
                    MediaObject.kind.in_(BOOK_KINDS),
                    MediaObject.status == "active",
                )
            ):
                key = fold(title)
                if key not in by_title or (available and not by_title[key].available):
                    by_title[key] = _Owned(object_id, bool(available), title)
    images = await posters(module.database, [o.object_id for o in (*known.values(), *by_title.values())])
    matched = [known.get(credit.tmdb_id) or by_title.get(fold(credit.title)) for credit in books]
    # a library book is one of them only (the most voted for: a whole book rather than its split part)
    claimed: dict[UUID, int] = {}
    for index, found in enumerate(matched):
        if found is not None:
            best = claimed.get(found.object_id)
            if best is None or books[index].vote_count > books[best].vote_count:
                claimed[found.object_id] = index
    out = []
    for index, credit in enumerate(books):
        found = matched[index]
        if found is not None and claimed[found.object_id] != index:
            found = None  # told by another
        status: Status = ("available" if found.available else "unavailable") if found else "absent"
        out.append(
            FilmCreditOut(
                tmdb_id=credit.tmdb_id,
                kind="book",
                title=found.title if found else credit.title,
                year=credit.year,
                role=None,
                department=credit.department,
                poster=None,
                image_id=images.get(found.object_id) if found else None,
                rating=credit.vote_average,
                votes=credit.vote_count,
                status=status,
                object_id=str(found.object_id) if found else None,
                # #367: absent, its sheet as the book database tells it
                route=f"/media/{found.object_id}" if found else sheet(credit.tmdb_id),
                cover=cover(credit.poster),
                position=credit.position,
            )
        )
    return out


def _profile(record: PersonRecord) -> PersonProfileOut:
    return PersonProfileOut(
        biography=record.biography,
        birthday=record.birthday,
        deathday=record.deathday,
        place_of_birth=record.place_of_birth,
        known_for=record.known_for,
        popularity=record.popularity,
        also_known_as=list(record.also_known_as),
        imdb=record.ids.get("imdb"),
    )


def _known_for(filmography: Sequence[FilmCreditOut]) -> list[FilmCreditOut]:
    """Their best-known titles — the most voted for — once each."""
    seen: set[tuple[str, str]] = set()
    out = []
    for credit in sorted(filmography, key=lambda c: -c.votes):
        if (credit.kind, credit.tmdb_id) not in seen and credit.votes:
            seen.add((credit.kind, credit.tmdb_id))
            out.append(credit)
        if len(out) >= KNOWN_FOR:
            break
    return out


@router.get("/media/person", response_model=PersonOut)
async def person(
    principal: Reader, module: Module, name: Annotated[str, Query(min_length=1, max_length=200)]
) -> PersonOut:
    page = await module.people.page(name)
    if page is None:
        raise PersonNotFound(f"no title credits {name[:60]!r}")
    ids = {object_id for titles in page.works.values() for object_id in titles}
    async with module.database.session() as session:
        rows = {
            row.id: row
            for row in (await session.execute(select(MediaObject).where(MediaObject.id.in_(ids)))).scalars()
        }
    images = await posters(module.database, ids)
    profile = await module.profiles.profile(
        page.name,
        {"tmdb": page.ref} if page.ref else {},
        await module.member_language(principal),
        books=set(page.roles) <= {"author", "narrator"},
    )
    record = profile.record if profile else None
    filmography: list[FilmCreditOut] = []
    if record is not None:
        filmography = await _filmography(module, record.credits)
        # issue 362: their books (a book database's), found in the library as it identified the library's
        # own, or among their titles; those of the library it does not list too (a translation's split part)
        service = profile.books if profile else None
        known, candidates = await _identify(module, service, list(ids))
        listed = {credit.tmdb_id for credit in record.credits if credit.kind == "book"}
        unlisted = [found[0] for found in candidates if not listed & {c.tmdb_id for c in found}]
        # #371: a book the library holds in parts (a translation split in volumes) is told by its parts
        covered = {c.part_of for found in candidates for c in found if c.part_of} - set(known)
        books = [
            *(c for c in record.credits if not (c.kind == "book" and c.tmdb_id in covered)),
            *{c.tmdb_id: c for c in unlisted}.values(),
        ]
        filmography += await _bibliography(
            module,
            books,
            works=list(ids),
            known=known,
            cover=lambda ref: _cover_url(service, ref),
            sheet=lambda ref: _sheet_url(service, ref),
        )
        # the most recent first; the undated (announced, or minor) last
        filmography.sort(key=lambda c: (c.year is not None, c.year or 0, c.votes), reverse=True)
    counts: dict[str, int] = {}
    for credit in {(c.kind, c.tmdb_id): c for c in filmography}.values():
        counts[credit.status] = counts.get(credit.status, 0) + 1
    if profile and profile.portrait:  # the services' own portrait first (the largest)
        service, ref = profile.portrait
        portrait = f"/api/v1/media/person/portrait?{urlencode({'service': service, 'ref': ref})}"
    elif page.portrait:
        portrait = f"/api/v1/media/metadata-images?{urlencode({'ref': page.portrait, 'size': 'h632'})}"
    else:
        portrait = None
    askable = module.requestable.configured() and await module.authorizer.is_allowed(principal, MEDIA_REQUEST)
    library = {
        role: await _asked(module, [_card(rows[i], _image(images.get(i))) for i in titles if i in rows])
        for role, titles in page.works.items()
    }
    return PersonOut(
        name=page.name,
        portrait=portrait,
        askable=askable,
        sources=[source.name for source in profile.sources] if profile else [],
        roles=list(page.roles),
        titles=len(ids),
        credits=[PersonCreditOut(role=role, items=items) for role, items in library.items()],
        profile=_profile(record) if record else None,
        known_for=_known_for(filmography),
        filmography=filmography,
        counts=counts,
    )


@router.get("/media/person/portrait")
async def person_portrait(
    _: Reader,
    module: Module,
    service: Annotated[str, Query(pattern=r"^[0-9a-f-]{36}$")],
    ref: Annotated[str, Query(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_./-]+$")],
    size: Annotated[str, Query(pattern=r"^(w185|h632)$")] = "h632",
) -> Response:
    """A person's portrait from the service that has it (TMDB, Seerr, Jellyfin, Grimmory), through the
    portal: browsers never call the services."""
    try:
        data = await module.profiles.portrait(service, ref, size)
    except LookupError as exc:
        raise PersonNotFound("No such portrait.") from exc
    except Exception as exc:
        raise Unavailable(
            "The portrait cannot be fetched right now.", code="media.image_unavailable"
        ) from exc
    media_type = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )
