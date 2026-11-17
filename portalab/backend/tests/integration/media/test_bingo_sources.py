"""Issue 356 — the month's media bingo, the media's side: the squares a library can fill (enough titles of a
genre, an era, a country, a long film…), and which ones a member ticked this month — a film or an episode
watched to its end, a book, an audiobook or a game a quarter of an hour at a time, live TV half an hour over
the month, a review written, a title kept for later — each by the first title that did it."""

from datetime import timedelta
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.core.time import FixedClock
from portalab.modules.media import bingo
from portalab.modules.media.models import Activity, MediaObject, ObjectMetadata, TasteVerdict
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users


async def _library(media: MediaHarness, clock: FixedClock) -> dict[str, UUID]:
    one = media.service(1)
    media.library(one)
    films = [
        library_record(
            f"m{n}", title=f"Film {n}", year=1984 + n % 3, genres=["Horreur", "Comedy"], duration_s=9600.0
        )
        for n in range(6)
    ]
    await media.module.library.upsert(
        [
            *films,
            library_record("s1", kind="series", title="Hannibal", genres=["Drame"]),
            library_record("se1", kind="season", title="Season 1", parent="s1", position=1),
            library_record("e1", kind="episode", title="Apéritif", parent="se1", position=1),
            library_record("e2", kind="episode", title="Amuse-Bouche", parent="se1", position=2),
            library_record("b1", kind="book", title="Astérix", genres=["Bande dessinée"]),
            library_record("g1", kind="game", title="Super Metroid"),
        ],
        one,
    )
    async with media.database.unit_of_work() as uow:
        ids = {t: i for t, i in (await uow.session.execute(select(MediaObject.title, MediaObject.id))).all()}
        for n in range(6):
            uow.session.add(
                ObjectMetadata(
                    object_id=ids[f"Film {n}"],
                    provider="tmdb",
                    status="found",
                    language="fr",
                    data={"countries": ["JP"]},
                    fetched_at=clock.now(),
                )
            )
    return ids


async def _play(
    media: MediaHarness,
    clock: FixedClock,
    user: UUID,
    kind: str,
    obj: UUID | None,
    work: UUID | None,
    *,
    days: int = 2,
    watched_s: float = 3000.0,
    progress: float = 1.0,
    title: str = "",
) -> None:
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            Activity(
                service_id=media.service(2, "tautulli").service_id,
                ref=str(uuid4()),
                family="plex",
                priority=20,
                counted=True,
                external_user_id="1",
                user_id=user,
                kind=kind,
                title=title,
                object_id=obj,
                work_id=work,
                ids={},
                started_at=clock.now() - timedelta(days=days),
                watched_s=watched_s,
                duration_s=None,
                progress=progress,
                received_at=clock.now(),
            )
        )


async def test_the_squares_a_library_fills_and_a_member_ticks(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe")
    zoe = people["zoe"]
    ids = await _library(media, clock)
    keys = {c.key for c in await bingo.cells(media.database, year=clock.now().year)}
    assert {"genre:horror", "genre:comedy", "era:1980", "country:JP", "length:long"} <= keys
    assert {"series:pilot", "series:marathon", "review", "later"} <= keys
    assert not {"genre:drama", "kind:audiobook", "kind:comics", "kind:live", "era:1990"} & keys  # too few
    assert not {"kind:book", "kind:game"} & keys  # issue 497: in the library, but nobody reads or plays yet

    await _play(media, clock, zoe, "movie", ids["Film 0"], ids["Film 0"])
    await _play(media, clock, zoe, "movie", ids["Film 1"], ids["Film 1"], days=1, progress=0.4)  # left early
    await _play(media, clock, zoe, "episode", ids["Apéritif"], ids["Hannibal"])
    await _play(media, clock, zoe, "game", ids["Super Metroid"], ids["Super Metroid"], watched_s=300.0)
    await _play(media, clock, zoe, "live", None, None, watched_s=1000.0, title="Kaamelott")
    await _play(media, clock, zoe, "live", None, None, days=1, watched_s=900.0, title="Le Discours")
    await _play(media, clock, zoe, "movie", ids["Film 2"], ids["Film 2"], days=40)  # last month
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            TasteVerdict(user_id=zoe, object_id=ids["Film 0"], verdict="later", updated_at=clock.now())
        )
    await login(client, "zoe")
    assert (
        await client.put(f"/api/v1/media/{ids['Film 0']}/reviews/mine", json={"rating": 5})
    ).status_code == 200

    wanted = [
        "genre:horror",
        "genre:drama",
        "era:1980",
        "country:JP",
        "length:long",
        "series:pilot",
        "series:marathon",
        "kind:game",
        "kind:live",
        "review",
        "later",
    ]
    found = await bingo.ticks(
        media.database, wanted, clock.now() - timedelta(days=30), clock.now() + timedelta(days=1)
    )
    mine = found[zoe]
    assert set(mine) == {
        "genre:horror",
        "genre:drama",
        "era:1980",
        "country:JP",
        "length:long",
        "series:pilot",
        "kind:live",
        "review",
        "later",
    }  # a game played 5 minutes (issue 497: 10 over the month), one episode of a series: not yet
    assert mine["genre:horror"].title == "Film 0" and mine["genre:horror"].object_id == ids["Film 0"]
    assert mine["series:pilot"].title == "Hannibal"  # an episode stands for its series
    assert mine["kind:live"].object_id is None and mine["kind:live"].title == "Le Discours"  # the 30th minute
    assert mine["review"].object_id == ids["Film 0"]


async def test_reading_playing_and_listening_weigh_on_the_card(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    """Issue 497: reading (a book's genre), playing (a console, a game's genre) and listening squares —
    offered only when someone used that kind on the portal lately; reading and playing add up over the
    month."""
    zoe = (await users(app, media, "zoe"))["zoe"]
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            *(
                library_record(
                    f"g{n}", kind="game", title=f"Jeu {n}", platform="Game Boy", genres=["Shooter"]
                )
                for n in range(6)
            ),
            *(library_record(f"b{n}", kind="book", title=f"Livre {n}", genres=["Fantasy"]) for n in range(6)),
        ],
        one,
    )
    async with media.database.session() as session:
        ids = {t: i for t, i in (await session.execute(select(MediaObject.title, MediaObject.id))).all()}
    lately = clock.now() - timedelta(days=90)
    assert not {k.key for k in await bingo.cells(media.database, year=2026, lately=lately)} & {
        "kind:game",
        "kind:book",
        "kind:radio",
    }  # nobody played, read or listened lately

    await _play(media, clock, zoe, "game", ids["Jeu 0"], ids["Jeu 0"], days=3, watched_s=240.0)
    await _play(media, clock, zoe, "game", ids["Jeu 1"], ids["Jeu 1"], days=2, watched_s=420.0)
    await _play(media, clock, zoe, "book", ids["Livre 0"], ids["Livre 0"], days=2, watched_s=500.0)
    await _play(media, clock, zoe, "book", ids["Livre 1"], ids["Livre 1"], days=1, watched_s=500.0)
    await _play(media, clock, zoe, "radio", None, None, days=200, watched_s=4000.0, title="Retro Rock")
    cells = {c.key: c.group for c in await bingo.cells(media.database, year=2026, lately=lately)}
    assert {
        key: cells.get(key) for key in ("kind:game", "play:shooter", "platform:Game Boy")
    } == dict.fromkeys(("kind:game", "play:shooter", "platform:Game Boy"), "play")
    assert cells.get("kind:book") == cells.get("read:fantasy") == "read"
    assert "kind:radio" not in cells  # listened to, but more than 90 days ago

    found = (
        await bingo.ticks(
            media.database,
            ["kind:game", "play:shooter", "platform:Game Boy", "kind:book", "read:fantasy"],
            clock.now() - timedelta(days=30),
            clock.now() + timedelta(days=1),
        )
    )[zoe]
    # 4 + 7 minutes of play: ticked by the second game; 8 + 8 minutes of reading: by the second book
    assert {key: tick.title for key, tick in found.items()} == {
        "kind:game": "Jeu 1",
        "play:shooter": "Jeu 1",
        "platform:Game Boy": "Jeu 1",
        "kind:book": "Livre 1",
        "read:fantasy": "Livre 1",
    }
