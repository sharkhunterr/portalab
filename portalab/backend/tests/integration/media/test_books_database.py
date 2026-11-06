"""Issue 362 — with a book database (Hardcover): an author's page tells their books, found in the library as
the database identified the library's own (from every identifier the library holds) or by their title (else
absent: no service asks for books), told by the library's title, with their covers through the portal,
beside every film or series they took part in; a library book it lists none of is told too; a book series'
page lists every volume."""

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.isolation import IsolationPolicy, ProviderGuard
from portalab.capabilities.media import (
    BOOK_SERIES,
    PEOPLE,
    BookDetails,
    BookEdition,
    BookSeries,
    BookSeriesProvider,
    OwnedBook,
    PeopleProvider,
    PersonCredit,
    PersonRecord,
)
from portalab.capabilities.media.testkit import library_record
from portalab.modules.connectors.breaker.breaker import CircuitBreaker
from portalab.modules.connectors.services.providers import guarded_provider
from portalab.modules.media.models import ExternalId, MediaObject
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

APPRENTICE = PersonCredit(
    tmdb_id="101",
    kind="book",
    title="Assassin's Apprentice",
    year=1995,
    department="writing",
    poster="/edition/1/apprentice.jpg",
    vote_count=3000,
    position=1,
)
ROYAL = PersonCredit(
    tmdb_id="102", kind="book", title="Royal Assassin", year=1996, department="writing", position=2
)
QUEST = PersonCredit(
    tmdb_id="103", kind="book", title="Assassin's Quest", year=1997, department="writing", position=3
)
BOOKS = (APPRENTICE, ROYAL, QUEST)
# the library's « Le Prophète blanc »: a split part of a book, listed in no bibliography
SPLIT = PersonCredit(tmdb_id="917", kind="book", title="The Golden Fool, Part 1", department="writing")


class _Hardcover:
    def __init__(self) -> None:
        self.series_asked: list[tuple[str, list[str]]] = []
        self.identified: list[OwnedBook] = []

    async def person(self, name: str, ids: Mapping[str, str], language: str) -> PersonRecord | None:
        if name != "Robin Hobb":
            return None
        return PersonRecord(
            ids={"hardcover": "204214"}, name=name, biography="An American writer.", credits=BOOKS
        )

    async def portrait(self, ref: str, size: str) -> bytes:
        return b"\xff\xd8cover" + ref.encode()

    async def identify(self, books: Sequence[OwnedBook]) -> Mapping[str, Sequence[PersonCredit]]:
        self.identified += books
        found: dict[str, Sequence[PersonCredit]] = {}
        for book in books:
            if "9780553573398" in book.ids.get("isbn", ()):
                found[book.key] = [APPRENTICE]
            elif "le-prophete-blanc" in book.ids.get("hardcover", ()):
                found[book.key] = [SPLIT]
        return found

    async def series(self, name: str, known: Sequence[str]) -> BookSeries | None:
        self.series_asked.append((name, list(known)))
        return BookSeries(
            ids={"hardcover": "8"}, name="The Farseer Trilogy", author="Robin Hobb", volumes=BOOKS
        )

    async def book(self, ref: str) -> BookDetails | None:
        if ref != "102":
            return None
        return BookDetails(
            ref="102",
            title="Royal Assassin",
            description="Fitz at court.",
            year=1996,
            pages=580,
            cover="/edition/2/royal.jpg",
            authors=["Robin Hobb"],
            series=[("L'Assassin royal", 2.0), ("The Realm of the Elderlings", 2.0)],
            genres=["Fantasy"],
            rating=8.4,
            votes=900,
            editions=[
                BookEdition(
                    title="L'Assassin du roi", language="fr", format="Read", ids={"isbn": ["9782290302529"]}
                ),
                BookEdition(title="Royal Assassin", language="en", format="Listened", audio=True),
            ],
        )

    async def cover(self, ref: str, size: str) -> bytes:
        return b"\xff\xd8cover" + ref.encode()


class _Films:
    """A film service: a film they played in, a series they wrote."""

    async def person(self, name: str, ids: Mapping[str, str], language: str) -> PersonRecord | None:
        return PersonRecord(
            ids={"tmdb": "1"},
            name=name,
            credits=[
                PersonCredit(tmdb_id="500", kind="movie", title="A Cameo", department="cast"),
                PersonCredit(tmdb_id="501", kind="series", title="Farseer", department="writing", year=2027),
            ],
        )

    async def portrait(self, ref: str, size: str) -> bytes:
        return b""


def _guarded(provider: Any, protocol: type[Any], capability: str) -> Any:
    """As a configured service's provider: behind the guard, which shows only the protocol's members."""
    return guarded_provider(
        provider,
        protocol,
        capability=capability,
        guard=ProviderGuard(source_system="test", policy=IsolationPolicy(max_retries=0)),
        breaker=CircuitBreaker(threshold=2, open_seconds=30),
        usable=lambda: True,
    )


async def _library(app: FastAPI, media: MediaHarness) -> _Hardcover:
    await users(app, media, "zoe")
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            # its French edition, found by its ISBN
            library_record(
                "b1",
                kind="book",
                title="L'Apprenti assassin",
                series="L'Assassin royal",
                series_position=1,
                authors=["Robin Hobb"],
                people=["Robin Hobb"],
            ),
            # found by its title
            library_record(
                "b2", kind="book", title="Royal Assassin", authors=["Robin Hobb"], people=["Robin Hobb"]
            ),
            # the series' third volume under another title, found by its number on the series' page
            library_record(
                "b3",
                kind="book",
                title="La Nef du crépuscule",
                series="L'Assassin royal",
                series_position=3,
                authors=["Robin Hobb"],
                people=["Robin Hobb"],
            ),
            library_record(
                "b4", kind="book", title="Le Prophète blanc", authors=["Robin Hobb"], people=["Robin Hobb"]
            ),
        ],
        one,
    )
    async with media.database.unit_of_work() as uow:
        first = (
            await uow.session.execute(select(MediaObject).where(MediaObject.title == "L'Apprenti assassin"))
        ).scalar_one()
        uow.session.add(ExternalId(scheme="isbn", value="9780553573398", object_id=first.id))
        split = (
            await uow.session.execute(select(MediaObject).where(MediaObject.title == "Le Prophète blanc"))
        ).scalar_one()
        uow.session.add(ExternalId(scheme="hardcover", value="le-prophete-blanc", object_id=split.id))
    hardcover = _Hardcover()
    service = media.service(9, "hardcover")
    media.ev.full.identity.capabilities.provide(
        PEOPLE,
        _guarded(hardcover, PeopleProvider, PEOPLE),
        instance_ref=str(service.service_id),
        owner=f"service:{service.service_id}",
        metadata={"connector": "hardcover", "name": "Hardcover"},
    )
    media.provide(BOOK_SERIES, service, _guarded(hardcover, BookSeriesProvider, BOOK_SERIES))
    films = media.service(7, "tmdb")
    media.ev.full.identity.capabilities.provide(
        PEOPLE,
        _Films(),
        instance_ref=str(films.service_id),
        owner=f"service:{films.service_id}",
        metadata={"connector": "tmdb", "name": "TMDB"},
    )
    return hardcover


async def _id(media: MediaHarness, title: str) -> str:
    async with media.database.session() as session:
        return str(
            (await session.execute(select(MediaObject.id).where(MediaObject.title == title))).scalar_one()
        )


async def test_an_author_s_books(app: FastAPI, client: httpx.AsyncClient, media: MediaHarness) -> None:
    hardcover = await _library(app, media)
    await login(client, "zoe")
    page = (await client.get("/api/v1/media/person", params={"name": "Robin Hobb"})).json()
    assert page["profile"]["biography"] == "An American writer."
    standing = {(c["title"], c["kind"]): (c["status"], c["object_id"]) for c in page["filmography"]}
    assert standing == {
        # identified (its ISBN), told by the library's title
        ("L'Apprenti assassin", "book"): ("available", await _id(media, "L'Apprenti assassin")),
        ("Royal Assassin", "book"): ("available", await _id(media, "Royal Assassin")),  # its title
        ("Assassin's Quest", "book"): ("absent", None),
        ("Le Prophète blanc", "book"): ("available", await _id(media, "Le Prophète blanc")),  # unlisted
        # every part they took in films and series stays, whatever it was
        ("A Cameo", "movie"): ("missing", None),
        ("Farseer", "series"): ("missing", None),
    }
    apprentice = next(c for c in page["filmography"] if c["tmdb_id"] == "101")
    assert apprentice["route"].startswith("/media/") and apprentice["votes"] == 3000
    quest = next(c for c in page["filmography"] if c["tmdb_id"] == "103")
    assert quest["cover"] is None
    service = str(UUID(int=9))
    assert quest["route"] == f"/media/book?service={service}&ref=103"  # #367: its sheet
    assert apprentice["cover"].startswith("/api/v1/media/person/portrait?service=")
    cover = await client.get(apprentice["cover"])
    assert cover.status_code == 200 and cover.content == b"\xff\xd8cover/edition/1/apprentice.jpg"
    assert page["counts"] == {"available": 3, "absent": 1, "missing": 2}
    # every identifier the library holds, told to the database: it reads those it knows
    told = {book.title: dict(book.ids) for book in hardcover.identified}
    assert told["L'Apprenti assassin"] == {"isbn": ["9780553573398"]}
    assert told["Le Prophète blanc"] == {"hardcover": ["le-prophete-blanc"]}


async def test_a_book_series_volumes(app: FastAPI, client: httpx.AsyncClient, media: MediaHarness) -> None:
    hardcover = await _library(app, media)
    await login(client, "zoe")
    page = (await client.get("/api/v1/media/collection", params={"ref": "series:L'Assassin royal"})).json()
    assert hardcover.series_asked == [("L'Assassin royal", ["101"])]  # told apart by its identified volumes
    assert [(p["title"], p["position"], p["status"], p["object_id"]) for p in page["parts"]] == [
        ("L'Apprenti assassin", 1.0, "available", await _id(media, "L'Apprenti assassin")),
        ("Royal Assassin", 2.0, "absent", None),  # not one of the series' own titles in the library
        ("La Nef du crépuscule", 3.0, "available", await _id(media, "La Nef du crépuscule")),  # its number
    ]
    cover = await client.get(page["parts"][0]["cover"])
    assert cover.status_code == 200 and cover.content.startswith(b"\xff\xd8cover")
    assert (
        await client.get("/api/v1/media/book-covers", params={"service": "0" * 36, "ref": "/x.jpg"})
    ).status_code == 404


async def test_a_book_s_sheet(app: FastAPI, client: httpx.AsyncClient, media: MediaHarness) -> None:
    """#367: a book's sheet from the book database — and where the library has it (« Royal Assassin » by
    its title and author); its series linked when the library has some of its volumes."""
    await _library(app, media)
    await login(client, "zoe")
    service = str(UUID(int=9))
    sheet = (await client.get("/api/v1/media/book", params={"service": service, "ref": "102"})).json()
    assert sheet["title"] == "Royal Assassin" and sheet["pages"] == 580 and sheet["authors"] == ["Robin Hobb"]
    assert sheet["library"] == {"book": await _id(media, "Royal Assassin")}
    assert [(s["name"], s["route"] is not None) for s in sheet["series"]] == [
        ("L'Assassin royal", True),
        ("The Realm of the Elderlings", False),
    ]
    assert [(e["title"], e["language"], e["audio"]) for e in sheet["editions"]] == [
        ("L'Assassin du roi", "fr", False),
        ("Royal Assassin", "en", True),
    ]
    assert sheet["cover"].startswith("/api/v1/media/book-covers?service=")
    unknown = await client.get("/api/v1/media/book", params={"service": service, "ref": "999"})
    assert unknown.status_code == 404
    elsewhere = await client.get("/api/v1/media/book", params={"service": "0" * 36, "ref": "102"})
    assert elsewhere.status_code == 404
