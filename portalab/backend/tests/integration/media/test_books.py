"""#20, #21 — listening and reading in the portal: an audiobook or a book opens from a source offering
``media.audio`` or ``media.reading``; the audio is relayed with byte ranges, the book's file and a comic's
pages too, under a ticket only its member may use (and only for what it was opened for); where the member
stops is kept in the portal, written back to the library when it keeps this member's progress, and
published as activity; the settings turn each off."""

from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.media import AUDIO, READING
from portalab.capabilities.media.testkit import AUDIO_BYTES, FakeAudio, FakeReading, library_record
from portalab.core.time import FixedClock
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration


async def _object(media: MediaHarness, title: str) -> str:
    async with media.database.session() as session:
        found = (
            await session.execute(text("SELECT id FROM media.objects WHERE title = :t"), {"t": title})
        ).scalar_one()
    return str(found)


async def _library(media: MediaHarness) -> tuple[str, str, FakeAudio, FakeReading]:
    grimmory = media.service(5, "grimmory")
    await media.module.library.upsert(
        [
            library_record("a1", kind="audiobook", title="The Book"),
            library_record("b1", kind="book", title="A Novel"),
        ],
        grimmory,
    )
    audio = media.provide(AUDIO, grimmory, FakeAudio())
    reading = media.provide(READING, grimmory, FakeReading())
    return await _object(media, "The Book"), await _object(media, "A Novel"), audio, reading


async def test_listen_as_the_account_the_library_keeps(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "zoe", "max")
    audiobook, book, audio, _ = await _library(media)
    await media.module.links.claim(people["zoe"], media.service(5).service_id, "owner", verified=True)
    await login(client, "zoe")

    info = await client.get(f"/api/v1/media/{audiobook}/listen")
    assert info.status_code == 200, info.text
    body = info.json()
    assert body["synced"] is True and body["resume"]["position_s"] == 600.0  # where the library says
    assert [c["title"] for c in body["item"]["chapters"]] == ["One", "Two"]
    ticket = body["ticket"]
    base = f"/api/v1/media/listen/{ticket}"

    whole = await client.get(f"{base}/audio")
    assert whole.status_code == 200 and whole.content == AUDIO_BYTES
    assert whole.headers["accept-ranges"] == "bytes" and whole.headers["cache-control"] == "no-store"
    part = await client.get(f"{base}/audio", headers={"Range": "bytes=100-199"})
    assert part.status_code == 206 and part.content == AUDIO_BYTES[100:200]
    assert part.headers["content-range"] == "bytes 100-199/1024"
    assert audio.calls[-1] == ("owner", "open", (None, "bytes=100-199"))

    for seq, state, at in ((1, "playing", 620.0), (2, "playing", 640.0), (3, "paused", 700.0)):
        sent = await client.post(
            f"{base}/position", json={"state": state, "position_s": at, "duration_s": 3600, "seq": seq}
        )
        assert sent.status_code == 204, sent.text
    assert audio.calls[-1] == ("owner", "report", ("f1", 700.0))  # written back to the library
    events = [
        (name, payload["kind"], payload["position_s"])
        for name, payload, _ in await media.events("media.playback")
    ]
    assert ("media.playback_started", "audiobook", 620.0) in events
    assert ("media.playback_paused", "audiobook", 700.0) in events
    assert not any(name == "media.playback_progressed" for name, _, _ in events)  # at most every minute

    done = await client.post(
        f"{base}/position", json={"state": "finished", "position_s": 3600, "duration_s": 3600, "seq": 4}
    )
    assert done.status_code == 204
    finished = [p for name, p, _ in await media.events("media.playback") if name == "media.playback_finished"]
    assert finished and finished[0]["percent"] == 1.0 and finished[0]["via"] == "portal"  # #103

    # a listening ticket opens nothing else, and is nobody else's
    assert (await client.get(f"/api/v1/media/read/{ticket}/file/11.epub")).status_code == 404
    await login(client, "max")
    stolen = await client.get(f"{base}/audio")
    assert stolen.status_code == 404 and stolen.json()["code"] == "media.book_expired"
    assert (await client.get(f"/api/v1/media/{book}/listen")).status_code == 404  # a book is not audio


async def test_a_member_the_library_does_not_know_keeps_their_place_in_the_portal(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "max")
    audiobook, _, audio, _ = await _library(media)
    await login(client, "max")

    first = (await client.get(f"/api/v1/media/{audiobook}/listen")).json()
    assert first["synced"] is False and first["resume"] is None
    ticket = first["ticket"]
    await client.post(
        f"/api/v1/media/listen/{ticket}/position",
        json={"state": "paused", "position_s": 1234.5, "duration_s": 3600, "seq": 1},
    )
    assert not any(call[1] == "report" for call in audio.calls)  # nothing written to the library
    again = (await client.get(f"/api/v1/media/{audiobook}/listen")).json()
    assert again["resume"]["position_s"] == 1234.5

    # an unfinished audiobook is « under way » — even at a few percent (an hour of a long book)
    await media.dispatch()
    under_way = await media.module.history.continue_items(people["max"])
    assert [o.kind for _, o in under_way] == ["audiobook"]


async def test_read_a_book(app: FastAPI, client: httpx.AsyncClient, media: MediaHarness) -> None:
    people = await users(app, media, "zoe")
    _, book, _, reading = await _library(media)
    await media.module.links.claim(people["zoe"], media.service(5).service_id, "owner", verified=True)
    await login(client, "zoe")

    info = await client.get(f"/api/v1/media/{book}/read")
    assert info.status_code == 200, info.text
    body = info.json()
    assert [f["format"] for f in body["book"]["formats"]] == ["epub", "cbx"]
    assert body["resume"] == [
        {"format": "epub", "position": "epubcfi(/6/4!/4/2)", "percent": 0.25, "file_ref": None}
    ]
    base = f"/api/v1/media/read/{body['ticket']}"

    file = await client.get(f"{base}/file/11.epub")
    assert file.status_code == 200 and file.content.startswith(b"PK")
    assert file.headers["content-disposition"] == "attachment"
    assert file.headers["content-security-policy"] == "sandbox; default-src 'none'"
    assert (await client.get(f"{base}/file/../../etc")).status_code == 404
    assert (await client.get(f"{base}/file/11.exe")).status_code == 422

    assert (await client.get(f"{base}/pages/12.cbx")).json() == {"pages": [1, 2, 3]}
    page = await client.get(f"{base}/page/12.cbx/2")
    assert page.status_code == 200 and page.headers["content-type"] == "image/png"
    assert (await client.get(f"{base}/page/12.cbx/9")).status_code == 404

    sent = await client.post(
        f"{base}/position",
        json={
            "state": "paused",
            "format": "epub",
            "file_ref": "11.epub",
            "position": "epubcfi(/6/8!/4/2)",
            "percent": 0.4,
            "seconds": 300,
            "seq": 1,
        },
    )
    assert sent.status_code == 204, sent.text
    assert reading.calls[-1] == ("owner", "report", ("epub", "epubcfi(/6/8!/4/2)"))
    paused = [p for name, p, _ in await media.events("media.playback") if name == "media.playback_paused"]
    assert paused[-1]["kind"] == "book" and paused[-1]["percent"] == 0.4 and paused[-1]["position_s"] == 300

    # the portal's position is the more recent: it wins over the library's older one
    resume = (await client.get(f"/api/v1/media/{book}/read")).json()["resume"]
    assert resume[0]["position"] == "epubcfi(/6/8!/4/2)" and resume[0]["file_ref"] == "11.epub"

    almost = await client.post(
        f"{base}/position",
        json={"state": "playing", "format": "epub", "position": "epubcfi(/6/99)", "percent": 0.999, "seq": 2},
    )
    assert almost.status_code == 204
    assert any(name == "media.playback_finished" for name, _, _ in await media.events("media.playback"))


async def test_settings_turn_listening_and_reading_off(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    await users(app, media, "zoe")
    audiobook, book, _, _ = await _library(media)
    await login(client, "zoe")
    await media.configure("media.listening.enabled", False)
    off = await client.get(f"/api/v1/media/{audiobook}/listen")
    assert off.status_code == 403 and off.json()["code"] == "media.books_disabled"
    assert (await client.get(f"/api/v1/media/{book}/read")).status_code == 200
    await media.configure("media.reading.enabled", False)
    assert (await client.get(f"/api/v1/media/{book}/read")).json()["code"] == "media.books_disabled"


async def test_a_sitting_ends_even_when_the_page_goes_away_without_a_word(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    """#256: the minutes heard count once the sitting ends — the page leaving ends it, and one left paused (a
    phone's app closed) is ended by the sweep; a sitting is never counted twice."""
    await users(app, media, "max")
    audiobook, _, _, _ = await _library(media)
    await login(client, "max")

    async def report(ticket: str, state: str, at: float, seq: int) -> None:
        sent = await client.post(
            f"/api/v1/media/listen/{ticket}/position",
            json={"state": state, "position_s": at, "duration_s": 36000, "seq": seq},
        )
        assert sent.status_code == 204, sent.text

    async def endings() -> list[tuple[str, float]]:
        return [
            (name, payload.get("watched_s", 0.0))
            for name, payload, _ in await media.events("media.playback")
            if name in ("media.playback_abandoned", "media.playback_finished")
        ]

    # listened ten minutes, paused, then the phone's app was closed: nothing more is heard of it
    first = (await client.get(f"/api/v1/media/{audiobook}/listen")).json()["ticket"]
    await report(first, "playing", 100.0, 1)
    clock.advance(timedelta(minutes=10))
    await report(first, "paused", 700.0, 2)
    assert await media.module.books.sweep() == 0  # not yet: it may go on
    clock.advance(timedelta(minutes=31))
    assert await media.module.books.sweep() == 1
    assert await endings() == [("media.playback_abandoned", 600.0)]
    assert await media.module.books.sweep() == 0  # ended once

    # the next time, the page leaves (its sitting ends), then comes back from the browser's cache and plays
    # on: another sitting, ended in its turn — each counted once, the late close of an ended one adds nothing
    second = (await client.get(f"/api/v1/media/{audiobook}/listen")).json()["ticket"]
    await report(second, "playing", 700.0, 1)
    clock.advance(timedelta(minutes=5))
    await report(second, "stopped", 1000.0, 2)
    await report(second, "stopped", 1000.0, 3)
    clock.advance(timedelta(minutes=1))
    await report(second, "playing", 1000.0, 4)
    clock.advance(timedelta(minutes=4))
    await report(second, "stopped", 1240.0, 5)
    clock.advance(timedelta(minutes=31))
    assert await media.module.books.sweep() == 0
    assert await endings() == [
        ("media.playback_abandoned", 600.0),
        ("media.playback_abandoned", 300.0),
        ("media.playback_abandoned", 240.0),
    ]


async def test_a_chapter_skipped_is_not_heard(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    """#353: what a sitting heard is its progress report after report — a jump (a chapter picked further
    on, a skip back) counts nothing, however long the sitting."""
    await users(app, media, "max")
    audiobook, _, _, _ = await _library(media)
    await login(client, "max")
    ticket = (await client.get(f"/api/v1/media/{audiobook}/listen")).json()["ticket"]

    async def report(state: str, at: float, seq: int) -> None:
        sent = await client.post(
            f"/api/v1/media/listen/{ticket}/position",
            json={"state": state, "position_s": at, "duration_s": 36000, "seq": seq},
        )
        assert sent.status_code == 204, sent.text

    await report("playing", 1000.0, 1)  # chapter 5
    clock.advance(timedelta(minutes=10))
    await report("playing", 1600.0, 2)  # ten minutes heard
    clock.advance(timedelta(seconds=20))
    await report("playing", 6000.0, 3)  # picked chapter 8: a jump of over an hour in 20 s
    clock.advance(timedelta(minutes=20))
    await report("playing", 7200.0, 4)  # twenty minutes heard
    clock.advance(timedelta(seconds=10))
    await report("playing", 7000.0, 5)  # skipped back
    clock.advance(timedelta(seconds=30))
    await report("stopped", 7030.0, 6)
    ended = [
        payload["watched_s"]
        for name, payload, _ in await media.events("media.playback")
        if name == "media.playback_abandoned"
    ]
    assert ended == [1830.0]  # 10 + 20 min + the last 30 s — not the 100 min between its two ends


async def test_an_audiobook_stopped_past_the_administrators_threshold_is_finished(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    """#386: finished where the administrator says for audiobooks (95 % by default), as a film — not only
    at its very last second: stopping during the closing credits is having listened to it."""
    people = await users(app, media, "zoe")
    audiobook, _, _, _ = await _library(media)
    await media.module.links.claim(people["zoe"], media.service(5).service_id, "owner", verified=True)
    await login(client, "zoe")
    base = f"/api/v1/media/listen/{(await client.get(f'/api/v1/media/{audiobook}/listen')).json()['ticket']}"
    for seq, state, at in ((1, "playing", 3300.0), (2, "paused", 3380.0)):  # 94 %: not yet
        sent = await client.post(
            f"{base}/position", json={"state": state, "position_s": at, "duration_s": 3600, "seq": seq}
        )
        assert sent.status_code == 204, sent.text
    names = [name for name, _, _ in await media.events("media.playback")]
    assert "media.playback_finished" not in names
    stopped = await client.post(
        f"{base}/position", json={"state": "stopped", "position_s": 3450, "duration_s": 3600, "seq": 3}
    )
    assert stopped.status_code == 204
    events = await media.events("media.playback")
    finished = [p for name, p, _ in events if name == "media.playback_finished"]
    assert len(finished) == 1 and finished[0]["kind"] == "audiobook" and finished[0]["percent"] == 1.0
    assert not any(name == "media.playback_abandoned" for name, _, _ in events)
