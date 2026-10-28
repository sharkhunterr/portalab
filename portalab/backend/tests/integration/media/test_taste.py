"""Issue 190: each member's taste — drawn from what they watched and read and from what they said of a title —
and the recommendations made from it, each with its reason."""

from datetime import timedelta
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.media.models import Activity, MediaObject
from portalab.modules.media.participant import MediaParticipant
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users


async def _library(media: MediaHarness) -> dict[str, UUID]:
    one = media.service(1)
    media.library(one)
    nolan = {"directors": ["Christopher Nolan"]}
    await media.module.library.upsert(
        [
            library_record(
                "m1", title="Inception", year=2010, genres=["Science-Fiction", "Thriller"], **nolan
            ),
            library_record(
                "m2", title="Interstellar", year=2014, genres=["Science-Fiction", "Drame"], **nolan
            ),
            library_record("m3", title="Tenet", year=2020, genres=["Science-Fiction", "Action"], **nolan),
            library_record("m4", title="Love Actually", year=2003, genres=["Romance", "Comédie"]),
            library_record("m5", title="Notting Hill", year=1999, genres=["Romance", "Comédie"]),
            library_record("m6", title="Coup de foudre à Manhattan", year=2002, genres=["Romance"]),
            library_record(
                "b1",
                kind="book",
                title="Le Messie de Dune",
                genres=["Science Fiction"],
                authors=["Frank Herbert"],
            ),
            library_record(
                "b2",
                kind="book",
                title="Les Enfants de Dune",
                genres=["Science Fiction"],
                authors=["Frank Herbert"],
            ),
            *(
                library_record(f"b{n}", kind="book", title=title, genres=[genre], authors=[author])
                for n, (title, genre, author) in enumerate(
                    (
                        ("Orgueil et Préjugés", "Romance", "Jane Austen"),
                        ("Le Rouge et le Noir", "Classique", "Stendhal"),
                        ("Fondation", "Science Fiction", "Isaac Asimov"),
                    ),
                    start=3,
                )
            ),
            library_record("s1", kind="series", title="Hannibal", genres=["Drame", "Crime"]),
            library_record("se1", kind="season", title="Season 1", parent="s1", position=1),
            library_record("e1", kind="episode", title="Apéritif", parent="se1", position=1),
        ],
        one,
    )
    async with media.database.session() as session:
        return {
            title: i for title, i in (await session.execute(select(MediaObject.title, MediaObject.id))).all()
        }


async def _watched(media: MediaHarness, clock: FixedClock, user: UUID, work: UUID, progress: float) -> None:
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
                kind="movie",
                title="",
                object_id=work,
                work_id=work,
                ids={},
                started_at=clock.now() - timedelta(days=40),
                watched_s=7000.0,
                duration_s=8000.0,
                progress=progress,
                received_at=clock.now(),
            )
        )


async def test_recommendations_say_why_and_learn_from_verdicts(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe", "alex")
    ids = await _library(media)
    for title in ("Inception", "Interstellar"):
        await _watched(media, clock, people["zoe"], ids[title], 1.0)
    await _watched(media, clock, people["zoe"], ids["Love Actually"], 0.1)  # left early, long ago

    await login(client, "zoe")
    first = (await client.get("/api/v1/me/media/recommendations")).json()["items"]
    titles = [card["title"] for card in first]
    assert titles[0] == "Tenet" and "Inception" not in titles  # never what I saw
    assert first[0]["reason"]["kind"] == "director" and first[0]["reason"]["name"] == "Christopher Nolan"
    assert set(first[0]["reason"]["titles"]) == {"Inception", "Interstellar"}
    assert not {"Le Messie de Dune", "Les Enfants de Dune"} & set(titles)  # no book read: no books yet
    # the discovery shelf and the assistant's tool read the same taste
    shelf = (await client.get("/api/v1/media/discovery/recommended")).json()["items"]
    assert shelf[0]["title"] == "Tenet"

    # « not for me »: the romances go; « I like it » on a book brings its author's others
    assert (
        await client.put(f"/api/v1/me/media/taste/titles/{ids['Notting Hill']}", json={"verdict": "dislike"})
    ).json() == {"object_id": str(ids["Notting Hill"]), "verdict": "dislike"}
    liked = await client.put(
        f"/api/v1/me/media/taste/titles/{ids['Le Messie de Dune']}", json={"verdict": "like"}
    )
    assert liked.status_code == 200
    after = (await client.get("/api/v1/me/media/recommendations")).json()["items"]
    titles = [card["title"] for card in after]
    assert "Coup de foudre à Manhattan" not in titles and "Notting Hill" not in titles
    dune = next(card for card in after if card["title"] == "Les Enfants de Dune")
    assert dune["reason"] == {"kind": "author", "name": "Frank Herbert", "titles": ["Le Messie de Dune"]}
    books = (await client.get("/api/v1/me/media/recommendations", params={"kind": "book"})).json()["items"]
    # its author first, then the science fiction loved in films too — never what shares nothing with my taste
    assert [card["title"] for card in books] == ["Les Enfants de Dune", "Fondation"]

    # « later »: out of the recommendations, in its list
    await client.put(f"/api/v1/me/media/taste/titles/{ids['Tenet']}", json={"verdict": "later"})
    assert "Tenet" not in [
        c["title"] for c in (await client.get("/api/v1/me/media/recommendations")).json()["items"]
    ]
    later = (await client.get("/api/v1/me/media/taste/lists/later")).json()["items"]
    assert [(c["title"], c["verdict"]) for c in later] == [("Tenet", "later")]
    assert (await client.get(f"/api/v1/me/media/taste/titles/{ids['Tenet']}")).json()["verdict"] == "later"

    # an episode's verdict goes to its series
    episode = await client.put(f"/api/v1/me/media/taste/titles/{ids['Apéritif']}", json={"verdict": "like"})
    assert episode.json()["object_id"] == str(ids["Hannibal"])
    assert (await client.get(f"/api/v1/me/media/taste/titles/{ids['Hannibal']}")).json()["verdict"] == "like"

    # the cards to judge never hold a title judged already
    deck = (await client.get("/api/v1/me/media/taste/deck")).json()["items"]
    judged = {"Notting Hill", "Le Messie de Dune", "Tenet", "Hannibal"}
    assert deck and not judged & {card["title"] for card in deck}

    taste = (await client.get("/api/v1/me/media/taste")).json()
    assert taste["counts"] == {"dislike": 1, "like": 2, "later": 1}
    assert "Christopher Nolan" in [p["name"] for p in taste["people"]]
    assert taste["families"] == ["books", "video"] and taste["works"] >= 4

    # someone else's taste is their own
    await login(client, "alex")
    assert (await client.get("/api/v1/me/media/recommendations")).json()["items"] == []
    assert (await client.get("/api/v1/me/media/taste/lists/later")).json()["items"] == []

    # my verdicts go with my data, and are forgotten on request
    exported = await MediaParticipant(media.database).export(people["zoe"])
    assert sorted((r.data["title"], r.data["verdict"]) for r in exported if r.category == "media.taste") == [
        ("Hannibal", "like"),
        ("Le Messie de Dune", "like"),
        ("Notting Hill", "dislike"),
        ("Tenet", "later"),
    ]
    await login(client, "zoe")
    await client.delete(f"/api/v1/me/media/taste/titles/{ids['Hannibal']}")
    assert (await client.get(f"/api/v1/me/media/taste/titles/{ids['Hannibal']}")).json()["verdict"] is None
    assert (await client.delete("/api/v1/me/media/taste")).status_code == 204
    assert (await client.get("/api/v1/me/media/taste")).json()["counts"] == {}
    await client.put(f"/api/v1/me/media/taste/titles/{ids['Tenet']}", json={"verdict": "like"})
    await MediaParticipant(media.database).erase(people["zoe"], "final")
    assert not [
        r for r in await MediaParticipant(media.database).export(people["zoe"]) if r.category == "media.taste"
    ]


async def test_the_taste_widgets(app: FastAPI, media: MediaHarness, clock: FixedClock) -> None:
    people = await users(app, media, "zoe")
    ids = await _library(media)
    for title in ("Inception", "Interstellar"):
        await _watched(media, clock, people["zoe"], ids[title], 1.0)
    zoe, ctx = Principal(user_id=people["zoe"]), LocaleContext()
    for_you = media.widgets.get("media.for_you")
    deck = media.widgets.get("media.taste")
    assert for_you is not None and deck is not None
    shown = await for_you.provider.load(zoe, {"kind": "all"}, ctx)
    first = shown.data["items"][0]
    assert first["title"] == "Tenet" and first["route"] == f"/media/{ids['Tenet']}"
    assert first["reason"]["name"] == "Christopher Nolan"
    cards = (await deck.provider.load(zoe, {}, ctx)).data["items"]
    assert cards and all(card["title"] not in ("Inception", "Interstellar") or card["seen"] for card in cards)


async def test_a_member_may_keep_their_history_out_of_their_taste(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe")
    ids = await _library(media)
    for title in ("Inception", "Interstellar"):
        await _watched(media, clock, people["zoe"], ids[title], 1.0)
    await login(client, "zoe")
    assert (await client.get("/api/v1/me/media/recommendations")).json()["items"]
    paused = await client.put("/api/v1/me/preferences", json={"media.taste.useHistory": False})
    assert paused.status_code == 200, paused.text
    assert (await client.get("/api/v1/me/media/recommendations")).json()["items"] == []
    assert (await client.get("/api/v1/me/media/taste")).json()["use_history"] is False


async def test_games_played_count_and_nothing_is_said_seen(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    """What I played in RomM tells my taste in games as films tell it in films; whether I saw, read or played
    a title is the services' to say — no « seen » verdict."""
    people = await users(app, media, "zoe")
    one = media.service(1)
    media.library(one)
    game = {"kind": "game", "platform": "SNES"}
    await media.module.library.upsert(
        [
            library_record(
                "g1",
                title="Super Metroid",
                genres=["SNES", "Platform"],
                tags=["Metroid"],
                series="Metroid",
                **game,
            ),
            library_record(
                "g2",
                kind="game",
                title="Metroid Fusion",
                genres=["Game Boy Advance", "Platform"],
                tags=["Metroid"],
                series="Metroid",
                platform="Game Boy Advance",
            ),
            library_record(
                "g3", title="Tetris", genres=["Game Boy", "Puzzle"], kind="game", platform="Game Boy"
            ),
            library_record("g4", title="Mario Kart", genres=["SNES", "Racing"], tags=["Mario"], **game),
            library_record("g5", title="Columns", genres=["Sega Game Gear", "Puzzle"], kind="game"),
        ],
        one,
    )
    async with media.database.session() as session:
        ids = {t: i for t, i in (await session.execute(select(MediaObject.title, MediaObject.id))).all()}
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            Activity(
                service_id=media.service(3, "romm").service_id,
                ref="session:1",
                family="romm",
                priority=10,
                counted=True,
                external_user_id="1",
                user_id=people["zoe"],
                kind="game",
                title="Super Metroid",
                object_id=ids["Super Metroid"],
                work_id=ids["Super Metroid"],
                ids={},
                started_at=clock.now() - timedelta(days=3),
                watched_s=3 * 3600.0,
                received_at=clock.now(),
            )
        )
    await login(client, "zoe")
    games = (await client.get("/api/v1/me/media/recommendations", params={"kind": "game"})).json()["items"]
    assert games[0]["title"] == "Metroid Fusion"
    assert games[0]["reason"] == {"kind": "saga", "name": "Metroid", "titles": ["Super Metroid"]}
    assert "Super Metroid" not in [g["title"] for g in games]
    assert (await client.get("/api/v1/me/media/taste")).json()["families"] == ["games"]
    seen = await client.put(f"/api/v1/me/media/taste/titles/{ids['Tetris']}", json={"verdict": "seen"})
    assert seen.status_code == 422


async def test_something_different_off_my_beaten_track(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    """Beside the recommendations: a well-rated title of a genre I never go to, and a game of a saga I love in
    books though I play no games — never one of my recommendations, never a genre I set aside twice."""
    await users(app, media, "zoe")
    one = media.service(1)
    media.library(one)
    book = {"kind": "book", "rating": 8.0}
    await media.module.library.upsert(
        [
            library_record("b1", title="Dune", genres=["Science Fiction"], series="Dune", **book),
            library_record("b2", title="Fondation", genres=["Science Fiction"], **book),
            library_record("b3", title="Hypérion", genres=["Science Fiction"], **book),
            library_record("b4", title="Orgueil et Préjugés", genres=["Romance"], kind="book", rating=9.0),
            library_record("b5", title="Un roman sans lecteurs", genres=["Romance"], kind="book", rating=5.0),
            *(
                library_record(f"h{n}", title=title, genres=["Horreur"], **book)
                for n, title in enumerate(("Ça", "Shining", "Carrie"))
            ),
            library_record("g1", title="Dune II", kind="game", genres=["Strategy"], series="Dune"),
            library_record("g2", title="Tetris", kind="game", genres=["Puzzle"]),
        ],
        one,
    )
    async with media.database.session() as session:
        ids = {t: i for t, i in (await session.execute(select(MediaObject.title, MediaObject.id))).all()}
    await login(client, "zoe")
    assert (await client.get("/api/v1/me/media/taste/discover")).json()["items"] == []  # no taste yet
    for title, verdict in (
        ("Dune", "like"),
        ("Fondation", "like"),
        ("Ça", "dislike"),
        ("Shining", "dislike"),
    ):
        await client.put(f"/api/v1/me/media/taste/titles/{ids[title]}", json={"verdict": verdict})

    found = {
        c["title"]: c["reason"] for c in (await client.get("/api/v1/me/media/taste/discover")).json()["items"]
    }
    assert found == {
        "Orgueil et Préjugés": {"kind": "detour", "name": "Romance", "titles": []},
        "Dune II": {"kind": "bridge", "name": "Dune", "titles": ["Dune"]},
    }
    offered = [c["title"] for c in (await client.get("/api/v1/me/media/recommendations")).json()["items"]]
    assert "Hypérion" in offered and not set(found) & set(offered)
