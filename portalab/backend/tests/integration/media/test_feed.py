"""#299 — « Mon fil »: a member follows a person, a title and a genre the library knows (and nothing it does
not); the feed brings what arrived lately because of them — a film by a director followed, a series' new
episodes, a work of a genre — each once, with why; what came after they last read it is unread; following is
private, and goes with the member."""

from datetime import timedelta

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.core.time import FixedClock
from portalab.modules.media.models import Follow, MediaObject
from portalab.modules.media.participant import MediaParticipant
from tests.integration.content.conftest import Outbox
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users


async def test_my_feed_brings_what_i_follow(
    app: FastAPI, media: MediaHarness, client: httpx.AsyncClient, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe", "alex")
    library = media.service(1, "fake")
    media.library(library)
    await media.module.library.upsert(
        [
            library_record(
                "m1", title="Dune", year=2021, directors=["Denis Villeneuve"], genres=["Science fiction"]
            ),
            library_record("m2", title="Heat", year=1995, directors=["Michael Mann"], genres=["Crime"]),
            library_record("s1", kind="series", title="Lost", year=2004),
            library_record("se1", kind="season", title="Season 1", parent="s1", position=1),
            library_record("e1", kind="episode", title="Pilot", parent="se1", position=1),
        ],
        library,
    )
    async with media.database.session() as session:
        lost = (await session.execute(select(MediaObject.id).where(MediaObject.title == "Lost"))).scalar_one()

    await login(client, "zoe")
    follows = [
        {"kind": "person", "ref": "denis villeneuve"},  # however it is written: the library's name is kept
        {"kind": "title", "ref": str(lost)},
        {"kind": "genre", "ref": "Science fiction"},
    ]
    for body in follows:
        assert (await client.put("/api/v1/me/media/follows", json=body)).status_code == 200
    mine = (await client.get("/api/v1/me/media/follows")).json()["items"]
    assert {(f["kind"], f["label"]) for f in mine} == {
        ("person", "Denis Villeneuve"),
        ("title", "Lost"),
        ("genre", "Science fiction"),
    }
    # nothing the library does not know
    refused = await client.put("/api/v1/me/media/follows", json={"kind": "person", "ref": "Nobody Atall"})
    assert refused.status_code == 422

    feed = (await client.get("/api/v1/me/media/feed")).json()
    by_title = {item["title"]: item for item in feed["items"]}
    assert set(by_title) == {"Dune", "Lost"}  # Heat: nothing of it is followed
    assert {(b["kind"], b["label"]) for b in by_title["Dune"]["because"]} == {
        ("person", "Denis Villeneuve"),
        ("genre", "Science fiction"),
    }
    assert set(by_title["Lost"]["units"]) == {"S01", "S01E01"}
    assert feed["follows"] == 3 and feed["upcoming"] == []  # no people service: nothing announced

    # read, then a new episode arrives: one unread
    assert (await client.post("/api/v1/me/media/feed/seen")).status_code == 204
    zoe = people["zoe"]
    assert await media.module.feed.unread(zoe) == 0
    clock.advance(timedelta(hours=2))
    await media.module.library.upsert(
        [library_record("e2", kind="episode", title="Tabula Rasa", parent="se1", position=2)], library
    )
    assert await media.module.feed.unread(zoe) == 1
    lost_item = next(
        i for i in (await client.get("/api/v1/me/media/feed")).json()["items"] if i["title"] == "Lost"
    )
    assert lost_item["unread"] is True and "S01E02" in lost_item["units"]

    # private: another member's feed knows nothing of it
    assert await media.module.feed.follows(people["alex"]) == []
    assert await media.module.feed.unread(people["alex"]) == 0

    # unfollowing takes it out of the feed
    gone = await client.delete("/api/v1/me/media/follows", params={"kind": "title", "ref": str(lost)})
    assert gone.status_code == 204
    titles = {i["title"] for i in (await client.get("/api/v1/me/media/feed")).json()["items"]}
    assert titles == {"Dune"}

    # the follows go with the member
    await MediaParticipant(media.database).erase(zoe, "final")
    async with media.database.session() as session:
        assert (await session.execute(select(Follow).where(Follow.user_id == zoe))).first() is None


async def test_my_feed_tells_me_once_what_arrived(
    app: FastAPI, media: MediaHarness, clock: FixedClock
) -> None:
    zoe = (await users(app, media, "zoe"))["zoe"]
    library = media.service(1, "fake")
    media.library(library)
    await media.module.library.upsert(
        [library_record("m1", title="Dune", year=2021, directors=["Denis Villeneuve"])], library
    )
    clock.advance(timedelta(minutes=-5))
    await media.module.feed.follow(zoe, "person", "Denis Villeneuve")
    clock.advance(timedelta(minutes=5))
    outbox = Outbox()
    assert await media.module.feed.notify_due(outbox) == 1
    (notice,) = outbox.sent
    assert notice.category == "media.feed" and notice.action_url == "/feed"
    assert notice.params == {"count": 1, "title": "Dune"}
    assert await media.module.feed.notify_due(outbox) == 0  # told already
    clock.advance(timedelta(hours=1))
    await media.module.library.upsert(
        [library_record("m2", title="Blade Runner 2049", year=2017, directors=["Denis Villeneuve"])], library
    )
    assert await media.module.feed.notify_due(outbox) == 1
    assert outbox.sent[-1].params == {"count": 1, "title": "Blade Runner 2049"}  # only what came since
