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
