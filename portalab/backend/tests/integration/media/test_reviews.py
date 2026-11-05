"""#355: members' reviews — a rating from 1 to 5 and a few words if wanted, on a work the member watched,
read, listened to or played; one per member and work (an episode's goes to its series); the first one tells
the progression once; the others' reviews signed or « Anonymous »; mine exported and erased with my data."""

from datetime import timedelta
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.core.time import FixedClock
from portalab.modules.media.models import Activity, MediaObject, Review
from portalab.modules.media.participant import MediaParticipant
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users


async def _library(media: MediaHarness) -> dict[str, UUID]:
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record("m1", title="Inception", year=2010),
            library_record("m2", title="Tenet", year=2020),
            library_record("s1", kind="series", title="Hannibal"),
            library_record("se1", kind="season", title="Season 1", parent="s1", position=1),
            library_record("e1", kind="episode", title="Apéritif", parent="se1", position=1),
        ],
        one,
    )
    async with media.database.session() as session:
        return {
            title: i for title, i in (await session.execute(select(MediaObject.title, MediaObject.id))).all()
        }


async def _watched(
    media: MediaHarness, clock: FixedClock, user: UUID, obj: UUID, work: UUID, kind: str
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
                title="",
                object_id=obj,
                work_id=work,
                ids={},
                started_at=clock.now() - timedelta(days=2),
                watched_s=3000.0,
                duration_s=3000.0,
                progress=1.0,
                received_at=clock.now(),
            )
        )


async def _told(media: MediaHarness) -> list[int]:
    return [payload["rating"] for kind, payload, _ in await media.events() if kind == "media.reviewed"]


async def test_a_member_reviews_what_they_saw(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe", "alex")
    ids = await _library(media)
    await _watched(media, clock, people["zoe"], ids["Inception"], ids["Inception"], "movie")
    await _watched(media, clock, people["zoe"], ids["Apéritif"], ids["Hannibal"], "episode")
    await _watched(media, clock, people["alex"], ids["Inception"], ids["Inception"], "movie")

    await login(client, "zoe")
    unseen = await client.put(f"/api/v1/media/{ids['Tenet']}/reviews/mine", json={"rating": 4})
    assert unseen.status_code == 403 and unseen.json()["code"] == "media.review_unseen"
    assert (await client.get(f"/api/v1/media/{ids['Tenet']}/reviews")).json()["can_review"] is False
    bad = await client.put(f"/api/v1/media/{ids['Inception']}/reviews/mine", json={"rating": 6})
    assert bad.status_code == 422

    given = await client.put(
        f"/api/v1/media/{ids['Inception']}/reviews/mine", json={"rating": 5, "comment": "  Un chef-d'œuvre  "}
    )
    assert given.status_code == 200, given.text
    body = given.json()
    assert body["mine"]["rating"] == 5 and body["mine"]["comment"] == "Un chef-d'œuvre"
    assert body["count"] == 1 and body["average"] == 5.0 and body["items"] == []
    changed = await client.put(f"/api/v1/media/{ids['Inception']}/reviews/mine", json={"rating": 4})
    assert changed.json()["mine"] == {**changed.json()["mine"], "rating": 4, "comment": None}
    # an episode's review goes to its series
    episode = await client.put(f"/api/v1/media/{ids['Apéritif']}/reviews/mine", json={"rating": 3})
    assert episode.json()["object_id"] == str(ids["Hannibal"])
    assert await _told(media) == [5, 3]  # once per work, the first rating

    await login(client, "alex")
    seen = (await client.get(f"/api/v1/media/{ids['Inception']}/reviews")).json()
    assert seen["can_review"] is True and seen["mine"] is None
    [theirs] = seen["items"]
    assert theirs["rating"] == 4 and theirs["mine"] is False
    assert theirs["author"] in ("zoe", None) and (theirs["author"] is None) == (theirs["author_id"] is None)
    await client.put(f"/api/v1/media/{ids['Inception']}/reviews/mine", json={"rating": 2})
    both = (await client.get(f"/api/v1/media/{ids['Inception']}/reviews")).json()
    assert both["count"] == 2 and both["average"] == 3.0

    removed = await client.delete(f"/api/v1/media/{ids['Inception']}/reviews/mine")
    assert removed.status_code == 204
    assert (await client.get(f"/api/v1/media/{ids['Inception']}/reviews")).json()["count"] == 1

    participant = MediaParticipant(media.database)
    exported = [r for r in await participant.export(people["zoe"]) if r.category == "media.review"]
    assert sorted(r.data["title"] for r in exported) == ["Hannibal", "Inception"]
    await participant.erase(people["zoe"], "final")
    async with media.database.session() as session:
        assert (await session.scalar(select(Review).where(Review.user_id == people["zoe"]))) is None
