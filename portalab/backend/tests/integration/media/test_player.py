"""027 (#2) — the portal's player: a title plays from a source offering ``media.streaming``, as the member's
own linked account (or, when the administrator allows it, the service's account); streams are addressed by
a signed ticket only its member may use; playlists and segments are relayed; text subtitles come as cues;
the position is reported; the quality is capped by the settings; the player can be turned off."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.media import STREAMING
from portalab.capabilities.media.testkit import FakeStreaming, library_record
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration


async def _film(media: MediaHarness) -> tuple[str, FakeStreaming]:
    plex = media.service(3, "plex")
    await media.module.library.upsert([library_record("m1", title="Film", year=2020)], plex)
    fake = media.provide(STREAMING, plex, FakeStreaming())
    async with media.database.session() as session:
        from sqlalchemy import text

        object_id = (
            await session.execute(text("SELECT id FROM media.objects WHERE title = 'Film'"))
        ).scalar_one()
    return str(object_id), fake


async def test_play_as_the_members_account(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe", "max")
    object_id, fake = await _film(media)
    await media.module.links.claim(people["zoe"], media.service(3).service_id, "7", verified=True)
    await login(client, "zoe")

    info = await client.get(f"/api/v1/media/{object_id}/player")
    assert info.status_code == 200, info.text
    body = info.json()
    assert body["linked"] is True and body["item"]["resume_s"] == 60.0
    assert body["qualities"][0] == "original" and "320k" in body["qualities"]
    assert [t["text"] for t in body["item"]["versions"][0]["subtitles"]] == [True, False]

    started = await client.post(
        f"/api/v1/media/{object_id}/player/start",
        json={"item": "m1", "quality": "20m", "subtitle": "s1", "duration_s": 6000},
    )
    assert started.status_code == 200, started.text
    stream = started.json()
    assert stream["subtitles"] == "text" and stream["video"] == "copy"
    ticket, playlist = stream["ticket"], stream["playlist"]
    assert fake.calls[-1][:2] == ("7", "start") and fake.calls[-1][2].quality == "20m"

    base = f"/api/v1/media/player/{ticket}"
    index = await client.get(f"{base}/{playlist}")
    assert index.status_code == 200 and index.text.startswith("#EXTM3U")
    assert index.headers["cache-control"] == "no-store"
    segment = await client.get(f"{base}/{playlist.rsplit('/', 1)[0]}/00000.ts")
    assert segment.status_code == 200 and segment.content == b"\x47" * 1880
    assert segment.headers["content-type"] == "video/mp2t"
    other = await client.get(f"{base}/session/someone-else/base/00000.ts")
    assert other.status_code == 404  # only this ticket's stream

    await client.get(f"{base}/subtitles", params={"at": 0})
    await asyncio.sleep(0.05)  # the feed reads in the background
    cues = (await client.get(f"{base}/subtitles", params={"at": 0})).json()["cues"]
    assert cues == [{"start_s": 1.0, "end_s": 2.5, "text": "Hello"}]  # « Later » is beyond the window

    picture = await client.get(f"{base}/image", params={"ref": "chapter:1:2"})
    assert picture.status_code == 200 and picture.headers["content-type"] == "image/jpeg"
    assert (await client.get(f"{base}/image", params={"ref": "chapter:9:9"})).status_code == 404
    assert (await client.get(f"{base}/image", params={"ref": "../etc"})).status_code == 422

    timeline = await client.post(f"{base}/timeline", json={"state": "paused", "position_s": 42.5})
    assert timeline.status_code == 204
    assert fake.calls[-1] == ("7", "report", ("paused", 42.5, 6000.0))
    assert (await client.post(f"{base}/stop")).status_code == 204
    assert fake.calls[-1][:2] == ("7", "stop")

    # a casting device: the remote playlist works without any session, and only with its remote ticket
    casting = await client.post(
        f"/api/v1/media/{object_id}/player/start",
        json={"item": "m1", "remote": True, "subtitle": "s1", "burn": True},
    )
    remote_path = casting.json()["remote_playlist"]
    assert remote_path.startswith("/api/v1/media/remote/") and casting.json()["subtitles"] == "burn"
    async with httpx.AsyncClient(transport=client._transport, base_url="https://portal.test") as device:
        fetched = await device.get(remote_path)
        assert fetched.status_code == 200 and fetched.headers["access-control-allow-origin"] == "*"
        player_ticket = casting.json()["ticket"]
        assert (await device.get(f"/api/v1/media/remote/{player_ticket}/{playlist}")).status_code == 404
        assert (await device.get(f"/api/v1/media/player/{player_ticket}/{playlist}")).status_code == 401
    assert started.json().get("remote_playlist") is None  # only when asked for

    # back to zero, without playing
    reset = await client.post(f"/api/v1/media/{object_id}/player/reset", json={"item": "m1"})
    assert reset.status_code == 204 and fake.calls[-1] == ("7", "reset", "m1")

    # someone else cannot use Zoé's ticket
    await login(client, "max")
    stolen = await client.get(f"{base}/{playlist}")
    assert stolen.status_code == 404 and stolen.json()["code"] == "media.player_expired"
    forged = await client.get(f"/api/v1/media/player/{ticket[:-4]}AAAA/{playlist}")
    assert forged.status_code == 404


async def test_unlinked_members_and_settings(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    await users(app, media, "max")
    object_id, fake = await _film(media)
    await login(client, "max")

    unlinked = await client.get(f"/api/v1/media/{object_id}/player")
    assert unlinked.status_code == 409 and unlinked.json()["code"] == "media.player_unlinked"

    await media.configure("media.player.ownerFallback", True)
    await media.configure("media.player.maxQuality", "4m")
    info = (await client.get(f"/api/v1/media/{object_id}/player")).json()
    assert info["linked"] is False and info["qualities"][0] == "4m"
    started = await client.post(
        f"/api/v1/media/{object_id}/player/start", json={"item": "m1", "subtitle": "s2"}
    )
    assert started.status_code == 200
    assert started.json()["subtitles"] == "burn"  # an image subtitle is burnt in
    assert fake.calls[-1][0] is None and fake.calls[-1][2].quality == "4m"  # the service's account, capped
    ticket = started.json()["ticket"]
    assert (await client.get(f"/api/v1/media/player/{ticket}/subtitles")).json() == {"cues": []}

    missing = await client.get(f"/api/v1/media/{object_id}/player", params={"item": "nope"})
    assert missing.status_code == 404 and missing.json()["code"] == "media.player_nothing"

    await media.configure("media.player.enabled", False)
    off = await client.get(f"/api/v1/media/{object_id}/player")
    assert off.status_code == 403 and off.json()["code"] == "media.player_disabled"


async def test_no_streaming_source_and_denied_account(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe")
    jelly = media.service(4, "jellyfin")
    await media.module.library.upsert([library_record("j1", title="Other", year=2001)], jelly)
    object_id, _ = await _film(media)
    await media.module.links.claim(people["zoe"], media.service(3).service_id, "denied", verified=True)
    await login(client, "zoe")
    from sqlalchemy import text

    async with media.database.session() as session:
        other = (
            await session.execute(text("SELECT id FROM media.objects WHERE title = 'Other'"))
        ).scalar_one()
    nothing = await client.get(f"/api/v1/media/{other}/player")
    assert nothing.status_code == 404 and nothing.json()["code"] == "media.player_nothing"
    denied = await client.get(f"/api/v1/media/{object_id}/player")
    assert denied.status_code == 403 and denied.json()["code"] == "media.player_denied"


async def test_continue_follows_the_servers_own_continue_watching(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    """#23: the media home's « Continue » shows what Plex itself has in progress for the member (a film
    paused a minute ago, before any history arrives), leaves out Plex history rows (Plex speaks for its
    titles: a title set back to zero leaves), and keeps other services' history (Grimmory)."""
    from datetime import timedelta
    from uuid import uuid4

    from portalab.capabilities.media import ResumePoint
    from portalab.modules.media.models import Activity
    from tests.integration.privacy.conftest import NOW

    people = await users(app, media, "zoe")
    plex = media.service(3, "plex")
    await media.module.library.upsert([library_record("m1", title="Film", year=2020)], plex)
    fake = FakeStreaming(
        resume=[ResumePoint("m1", "movie", "Film", position_s=1500, duration_s=6000, at=NOW)]
    )
    media.ev.full.identity.capabilities.provide(
        STREAMING, fake, instance_ref=str(plex.service_id), owner="service:3", metadata={"connector": "plex"}
    )
    await media.module.links.claim(people["zoe"], plex.service_id, "7", verified=True)
    async with media.database.unit_of_work() as uow:
        for title, family in (("Old Plex film", "plex"), ("A book", "grimmory")):
            uow.session.add(
                Activity(
                    service_id=uuid4(),
                    ref=str(uuid4()),
                    family=family,
                    priority=10,
                    counted=True,
                    external_user_id="7",
                    user_id=people["zoe"],
                    kind="movie" if family == "plex" else "book",
                    title=title,
                    ids={},
                    started_at=NOW - timedelta(days=2),
                    watched_s=100.0,
                    duration_s=1000.0,
                    progress=0.4,
                    received_at=NOW,
                )
            )
    await login(client, "zoe")
    shelf = (await client.get("/api/v1/me/media/journal")).json()["continue"]
    assert [(c["title"], c["progress"]) for c in shelf] == [("Film", 0.25), ("A book", 0.4)]
    assert shelf[0]["route"].startswith("/media/")  # tied to the catalog's object

    # an episode is shown by its series (the series' poster and page)
    await media.module.library.upsert(
        [
            library_record("s1", kind="series", title="Firefly"),
            library_record("e1", kind="episode", title="Pilot", parent="s1"),
        ],
        plex,
    )
    fake.resume.insert(
        0,
        ResumePoint("e1", "episode", "Pilot", parent_title="Firefly", label="S01E01", series_id="s1", at=NOW),
    )
    shelf = (await client.get("/api/v1/me/media/journal")).json()["continue"]
    async with media.database.session() as session:
        from sqlalchemy import text

        series = (
            await session.execute(text("SELECT id FROM media.objects WHERE title = 'Firefly'"))
        ).scalar_one()
    assert shelf[0]["route"] == f"/media/{series}" and shelf[0]["subtitle"] == "S01E01 · Pilot"
    fake.resume.pop(0)

    fake.resume.clear()  # « Back to zero » on Plex
    shelf = (await client.get("/api/v1/me/media/journal")).json()["continue"]
    assert [c["title"] for c in shelf] == ["A book"]
