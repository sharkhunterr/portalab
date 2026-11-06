"""Issue 361 — the collections of the library told the same way: a book's series (in its volumes' order),
a game's franchise (each copy with its platform), a film's saga; and the saga's page lists every film TMDB
knows of it, each available or to ask for."""

from datetime import UTC, datetime

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.isolation import IsolationPolicy, ProviderGuard
from portalab.capabilities.media import METADATA, MetadataProvider, PersonCredit
from portalab.capabilities.media.testkit import library_record
from portalab.modules.connectors.breaker.breaker import CircuitBreaker
from portalab.modules.connectors.services.providers import guarded_provider
from portalab.modules.media.models import ExternalId, MediaObject, ObjectMetadata
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

SAGA = {"id": "531241", "name": "Spider-Man (MCU) - Saga", "poster": "/saga.jpg", "backdrop": None}


class _Tmdb:
    """The metadata provider: a saga's films."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    async def lookup(self, *_: object) -> None:
        return None

    async def fetch_image(self, ref: str, size: str) -> bytes:
        return b""

    async def role_images(self, person_id: str) -> list[object]:
        return []

    async def saga(self, collection_id: str, language: str) -> list[PersonCredit] | None:
        self.asked.append(collection_id)
        if collection_id != SAGA["id"]:
            return None
        return [
            PersonCredit(tmdb_id="634649", kind="movie", title="No Way Home", year=2021, department="saga"),
            PersonCredit(tmdb_id="315635", kind="movie", title="Homecoming", year=2017, department="saga"),
        ]


async def _id(media: MediaHarness, title: str) -> str:
    async with media.database.session() as session:
        return str(
            (await session.execute(select(MediaObject.id).where(MediaObject.title == title))).scalar_one()
        )


async def _library(app: FastAPI, media: MediaHarness) -> None:
    await users(app, media, "zoe")
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record(
                "b2",
                kind="book",
                title="Aliens: Fire and Stone 2",
                series="Fire and Stone",
                series_position=2,
            ),
            library_record(
                "b1",
                kind="book",
                title="Prometheus: Fire and Stone",
                series="Fire and Stone",
                series_position=1,
            ),
            library_record("b3", kind="book", title="Fire and Stone: Omega", series="fire and stone"),
            library_record(
                "g1",
                kind="game",
                title="Crash Team Racing",
                series="Crash Bandicoot",
                platform="PlayStation",
                year=1999,
            ),
            library_record(
                "g2",
                kind="game",
                title="Crash Bash",
                series="Crash Bandicoot",
                platform="PlayStation",
                year=2000,
            ),
            library_record("g3", kind="game", title="Wall Crash"),
            library_record("m1", title="Spider-Man: Homecoming", year=2017),
            library_record("m2", title="Spider-Man: Far From Home", year=2019),
        ],
        one,
    )
    async with media.database.unit_of_work() as uow:
        for title, tmdb in (("Spider-Man: Homecoming", "315635"), ("Spider-Man: Far From Home", "429617")):
            film = (
                await uow.session.execute(select(MediaObject).where(MediaObject.title == title))
            ).scalar_one()
            uow.session.add(ExternalId(scheme="tmdb", value=tmdb, object_id=film.id))
            uow.session.add(
                ObjectMetadata(
                    object_id=film.id,
                    provider="tmdb",
                    status="found",
                    language="fr",
                    data={"collection": SAGA},
                    fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )


async def test_a_book_s_series_and_a_game_s_franchise(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    await _library(app, media)
    await login(client, "zoe")
    book = await _id(media, "Aliens: Fire and Stone 2")
    series = (await client.get(f"/api/v1/media/{book}/collection")).json()
    assert (series["ref"], series["source"], series["name"]) == (
        "series:Fire and Stone",
        "series",
        "Fire and Stone",
    )
    # its volumes in order, whatever case they write the series in; the one without a volume last
    assert [(i["title"], i["position"]) for i in series["items"]] == [
        ("Prometheus: Fire and Stone", 1.0),
        ("Aliens: Fire and Stone 2", 2.0),
        ("Fire and Stone: Omega", None),
    ]
    game = await _id(media, "Crash Bash")
    franchise = (await client.get(f"/api/v1/media/{game}/collection")).json()
    assert franchise["name"] == "Crash Bandicoot"
    assert [(i["title"], i["platform"]) for i in franchise["items"]] == [
        ("Crash Team Racing", "PlayStation"),
        ("Crash Bash", "PlayStation"),
    ]
    page = (await client.get("/api/v1/media/collection", params={"ref": "series:crash bandicoot"})).json()
    assert page["ref"] == "series:Crash Bandicoot" and len(page["items"]) == 2 and page["parts"] == []
    # a title of no collection: nothing to tell
    alone = await client.get(f"/api/v1/media/{await _id(media, 'Wall Crash')}/collection")
    assert alone.status_code == 200 and alone.json() is None
    for ref in ("series:Nothing", "tmdb:12", "nothing"):
        assert (await client.get("/api/v1/media/collection", params={"ref": ref})).status_code == 404


async def test_a_film_s_saga_and_its_page(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    await _library(app, media)
    tmdb = _Tmdb()
    service = media.service(5, "tmdb")
    # as a configured service's provider: behind the guard, which shows only the protocol's members
    guarded = guarded_provider(
        tmdb,
        MetadataProvider,
        capability=METADATA,
        guard=ProviderGuard(source_system="tmdb", policy=IsolationPolicy(max_retries=0)),
        breaker=CircuitBreaker(threshold=2, open_seconds=30),
        usable=lambda: True,
    )
    media.provide(METADATA, service, guarded)
    await login(client, "zoe")
    home = await _id(media, "Spider-Man: Homecoming")
    saga = (await client.get(f"/api/v1/media/{home}/collection")).json()
    assert (saga["ref"], saga["source"], saga["name"], saga["poster"]) == (
        "tmdb:531241",
        "saga",
        "Spider-Man (MCU) - Saga",
        "/saga.jpg",
    )
    assert [i["title"] for i in saga["items"]] == ["Spider-Man: Homecoming", "Spider-Man: Far From Home"]
    assert tmdb.asked == []  # a title's page asks no service
    page = (await client.get("/api/v1/media/collection", params={"ref": "tmdb:531241"})).json()
    assert tmdb.asked == ["531241"]
    # every film of the saga in its order: the library's, and the one to ask for
    assert [(p["title"], p["status"], p["object_id"]) for p in page["parts"]] == [
        ("Homecoming", "available", home),
        ("No Way Home", "missing", None),
    ]
    assert len(page["items"]) == 2
