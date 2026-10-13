"""HTTP API of a person's page (#92): ``GET /media/person?name=…`` — an actor's, a director's, an author's,
a narrator's titles in the library, by role, with their portrait; and what the metadata provider (TMDB)
knows of them — biography, birth, what they are known for — with their whole filmography, each title told
available, asked for, not available or missing from the library (and then where to ask for it).
The name is a query parameter: a name may hold a slash (« AC/DC »)."""

from collections.abc import Sequence
from typing import Annotated, Literal
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel
from sqlalchemy import select

from portalab.capabilities.media import PersonCredit, PersonRecord
from portalab.core.errors import NotFound, Unavailable
from portalab.modules.media.api.router import MediaCard, Module, Reader, _asked, _card
from portalab.modules.media.models import ExternalId, MediaObject, MediaRequest
from portalab.modules.media.permissions import MEDIA_REQUEST
from portalab.modules.media.providers.insight_widgets import posters
from portalab.modules.media.requests.discovery import OPEN

router = APIRouter(prefix="/api/v1", tags=["media"])
KNOWN_FOR = 10
Status = Literal["available", "requested", "unavailable", "missing"]


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
