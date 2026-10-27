"""#111 — the catalog's filters: years, each kind's own fields (author, narrator, director, platform,
publisher, series, language), what the member already watched, read or played, the order and the total;
and the facets that fill the filters."""

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.modules.media.models import MediaObject, UserProgress
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users


async def _titles(client: httpx.AsyncClient, **params: Any) -> list[str]:
    page = (await client.get("/api/v1/media", params=params)).json()
    titles = [i["title"] for i in page["items"]]
    assert page["total"] == len(titles)
    return titles


async def test_catalog_filters_and_facets(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe")
    library = media.service(1, "fake")
    media.library(library)
    await media.module.library.upsert(
        [
            library_record(
                "b1",
                kind="book",
                title="Dune",
                year=1965,
                authors=["Frank Herbert"],
                series="Dune",
                language="en",
                genres=["Science fiction"],
            ),
            library_record(
                "b2",
                kind="book",
                title="Fondation",
                year=1951,
                authors=["Isaac Asimov"],
                language="fr",
                genres=["Science fiction"],
            ),
            library_record(
                "a1",
                kind="audiobook",
                title="Dune (audio)",
                year=2007,
                authors=["Frank Herbert"],
                narrators=["Scott Brick"],
            ),
            library_record(
                "g1",
                kind="game",
                title="Sonic",
                year=1991,
                platform="Sega Mega Drive/Genesis",
                publisher="Sega",
            ),
            library_record(
                "g2", kind="game", title="Tetris", year=1989, platform="Game Boy", publisher="Nintendo"
            ),
            library_record("m1", title="Heat", year=1995, directors=["Michael Mann"], genres=["Crime"]),
            library_record("m2", title="Alien", year=1979, directors=["Ridley Scott"], genres=["Horror"]),
            library_record("s1", kind="series", title="Lost", year=2004),
            library_record("e1", kind="episode", title="Pilot", parent="s1", position=1),
        ],
        library,
    )
    async with media.database.unit_of_work() as uow:
        ids = {o.title: o.id for o in (await uow.session.execute(select(MediaObject))).scalars()}
        now = datetime(2026, 10, 1, tzinfo=UTC)
        uow.session.add_all(
            [
                UserProgress(user_id=people["zoe"], object_id=ids["Heat"], resume_position_s=0, percent=1,
                             state="finished", last_occurred_at=now, finished_at=now),
                UserProgress(user_id=people["zoe"], object_id=ids["Pilot"], resume_position_s=60, percent=0.1,
                             state="in_progress", last_occurred_at=now),
            ]
        )  # fmt: skip
    await login(client, "zoe")

    assert await _titles(client, kind="book", author="frank herbert") == ["Dune"]
    assert await _titles(client, kind="book", author="herb") == ["Dune"]  # part of a name will do
    assert await _titles(client, kind="game", platform="Game") == []  # a platform is chosen whole
    assert await _titles(client, kind="audiobook", narrator="Scott Brick") == ["Dune (audio)"]
    assert await _titles(client, kind="book", language="fr") == ["Fondation"]
    assert await _titles(client, kind="book", series="Dune") == ["Dune"]
    assert await _titles(client, kind="game", platform="Game Boy") == ["Tetris"]
    assert await _titles(client, kind="game", publisher="sega") == ["Sonic"]
    assert await _titles(client, kind="movie", director="Ridley Scott") == ["Alien"]
    assert await _titles(client, kind="movie", year_from=1990, year_to=2000) == ["Heat"]
    assert await _titles(client, kind="game", sort="year") == ["Sonic", "Tetris"]
    # what I watched: a film finished, a series started from its episode
    assert await _titles(client, seen="finished") == ["Heat"]
    assert await _titles(client, seen="started") == ["Lost"]
    unseen = await _titles(client, kind="movie", seen="unseen")
    assert unseen == ["Alien"]

    books = (await client.get("/api/v1/media/facets", params={"kind": "book"})).json()
    assert set(books["authors"]) == {"Frank Herbert", "Isaac Asimov"}
    assert set(books["languages"]) == {"en", "fr"} and books["genres"] == ["Science fiction"]
    assert books["years"] == {"min": 1951, "max": 1965}
    games = (await client.get("/api/v1/media/facets", params={"kind": "game"})).json()
    assert set(games["platforms"]) == {"Sega Mega Drive/Genesis", "Game Boy"} and games["authors"] == []


async def test_an_episode_is_told_with_its_series_and_season(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    """#261: the catalog tells another module an episode with its series' title and its season's number."""
    people = await users(app, media, "zoe")
    library = media.service(1, "fake")
    media.library(library)
    await media.module.library.upsert(
        [
            library_record("s1", kind="series", title="Sissi", year=2021),
            library_record("se2", kind="season", title="Season 2", parent="s1", position=2),
            library_record("e6", kind="episode", title="Épisode 6", parent="se2", position=6),
            library_record("m1", title="Heat", year=1995),
        ],
        library,
    )
    async with media.database.session() as session:
        ids = {o.title: o.id for o in (await session.execute(select(MediaObject))).scalars()}
    viewer = Principal(user_id=people["zoe"])
    episode = await media.module.catalog_port.get(ids["Épisode 6"], viewer)
    assert episode is not None
    assert (episode.series, episode.season, episode.number) == ("Sissi", 2, 6)
    film = await media.module.catalog_port.get(ids["Heat"], viewer)
    assert film is not None and (film.series, film.season, film.number, film.year) == (None, None, None, 1995)
