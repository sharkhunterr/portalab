"""Issue 419 — a library's game played in the portal: whether a title plays here (its platform's emulator), a
sitting started, its files relayed to its player only while it is open, kept alive and ended by the page (or
by the sweep once the page went silent) — its minutes counted as the player's own portal sitting of a game
and told to the library once; a household profile's restrictions and screen time hold; switched off, it is
not there."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock
from portalab.modules.household.rules import RestrictionSettings
from portalab.modules.media.models import MediaObject
from portalab.modules.retro.models import Sitting
from portalab.modules.retro.module import RetroModule
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.retro.conftest import FakeRetro


async def _games(media: MediaHarness) -> dict[str, UUID]:
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record("r1", kind="game", title="Super Metroid"),
            library_record("r2", kind="game", title="Pong"),
            library_record("m1", title="Alien"),
        ],
        one,
    )
    async with media.database.session() as session:
        rows = (await session.execute(select(MediaObject.title, MediaObject.id))).all()
    return {title: object_id for title, object_id in rows}


async def _sitting(client: httpx.AsyncClient, object_id: UUID) -> dict[str, Any]:
    response = await client.post(f"/api/v1/retro/games/{object_id}/sittings")
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_a_member_plays_a_game_of_the_library(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe")
    ids = await _games(media)
    await login(client, "zoe")

    found = await client.get(f"/api/v1/retro/games/{ids['Super Metroid']}")
    assert found.status_code == 200, found.text
    assert found.json() == {
        "title": "Super Metroid",
        "platform": "snes",
        "core": "snes9x",
        "threads": False,
        "service_name": None,
        "progress": {"sram_at": None, "states": [], "latest_slot": None, "slots": 5},  # 420: nothing saved
        "engine": "emulatorjs",  # 421
        "control_scheme": None,
        "rom": "r1",  # 420: which copy, and every copy played here
        "variant": None,
        "roms": [
            {
                "id": "r1",
                "variant": None,
                "platform": "snes",
                "core": "snes9x",
                "engine": "emulatorjs",
                "size": 9,
                "progress": {"sram_at": None, "states": [], "latest_slot": None, "slots": 5},
            }
        ],
    }
    sitting = await _sitting(client, ids["Super Metroid"])
    base = f"/api/v1/retro/sittings/{sitting['id']}"
    assert sitting["game_url"] == f"{base}/game/Super%20Metroid%20%28E%29.sfc"
    assert sitting["game_name"] == "Super Metroid (E).sfc"
    assert sitting["firmware"] == [
        {"id": "5", "file_name": "bios.bin", "verified": True, "url": f"{base}/firmware/5/bios.bin"}
    ]
    assert sitting["emulator_path"] == f"/api/v1/retro/libraries/{UUID(int=1)}/emulator/"

    game = await client.get(sitting["game_url"], headers={"Range": "bytes=0-3"})
    assert game.status_code == 206 and game.headers["content-range"].startswith("bytes 0-")
    assert game.content == b"rom:Super Metroid (E).sfc" and game.headers["cache-control"] == "no-store"
    assert retro.opened[-1] == ("rom", "r1", "Super Metroid (E).sfc", "bytes=0-3")
    size = await client.head(sitting["game_url"])  # the emulator asks the size first
    assert size.status_code == 200 and size.headers["content-length"] == "9"
    assert len(retro.opened) == 1  # told from the library's record: nothing downloaded
    bios = await client.get(f"{base}/firmware/5/bios.bin")
    assert bios.status_code == 200 and bios.content == b"firmware:bios.bin"
    assert (await client.get(f"{base}/firmware/6/other.bin")).status_code == 404  # not this platform's
    assert (await client.head(f"{base}/firmware/5/bios.bin")).status_code == 200
    core = await client.get(f"{sitting['emulator_path']}cores/snes9x-wasm.data")
    assert core.status_code == 200 and core.headers["cache-control"] == "private, max-age=86400"
    loader = await client.get(f"{sitting['emulator_path']}loader.js")
    assert loader.headers["content-type"].startswith("text/javascript")  # typed by the portal
    page = await client.get(f"{sitting['emulator_path']}index.html")
    assert page.headers["content-type"] == "application/octet-stream"  # never a page of the library's
    assert (await client.get(f"{sitting['emulator_path']}..%2F..%2Fapi")).status_code in (404, 422)

    clock.advance(timedelta(seconds=30))
    beat = await client.post(f"{base}/beat")
    assert beat.status_code == 200 and beat.json() == {"minutes_left": None, "stop": False}
    clock.advance(timedelta(minutes=10))  # a tab asleep: at most one beat's gap counts
    assert (await client.post(f"{base}/end")).status_code == 204
    assert (await client.post(f"{base}/end")).status_code == 204  # the page leaving twice: once
    assert retro.sessions == [("r1", 120_000)]
    assert (await client.get(sitting["game_url"])).status_code == 404  # over: its files no longer

    events = await media.events("media.playback_")
    assert [name for name, _, _ in events] == ["media.playback_started", "media.playback_abandoned"]
    ended = events[-1][1]
    assert (ended["kind"], ended["via"], ended["watched_s"], ended["object"]) == (
        "game",
        "portal",
        120.0,
        str(ids["Super Metroid"]),
    )
    assert events[-1][2] == str(people["zoe"])


async def test_what_does_not_play_here(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    await users(app, media, "zoe")
    ids = await _games(media)
    await login(client, "zoe")
    for title in ("Pong", "Alien"):  # no emulator for its platform; not a game at all
        response = await client.get(f"/api/v1/retro/games/{ids[title]}")
        assert response.status_code == 404 and response.json()["code"] == "retro.not_playable", title
    retro.games["r1"] = replace(retro.games["r1"], present=False)  # the library lost its file
    assert (await client.get(f"/api/v1/retro/games/{ids['Super Metroid']}")).status_code == 404


async def test_a_sitting_is_its_players_only(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    await users(app, media, "zoe", "max")
    ids = await _games(media)
    await login(client, "zoe")
    sitting = await _sitting(client, ids["Super Metroid"])
    await login(client, "max")
    base = f"/api/v1/retro/sittings/{sitting['id']}"
    for method, path in (("GET", sitting["game_url"]), ("POST", f"{base}/beat"), ("POST", f"{base}/end")):
        response = await client.request(method, path)
        assert response.status_code == 404 and response.json()["code"] == "retro.sitting_not_found", path


async def test_a_profile_plays_within_its_masters_rules(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro, clock: FixedClock
) -> None:
    people = await users(app, media, "zoe")
    ids = await _games(media)
    households = app.state.household_module.service
    owner = Principal(user_id=people["zoe"])
    lea = UUID(
        str((await households.create(owner, display_name="Léa", kind="standard", color=None, pin=None))["id"])
    )
    await households.change(owner, lea, restrictions=RestrictionSettings(daily_minutes=15))
    clock.set(datetime.now(UTC) - timedelta(minutes=20))  # today, as the screen time's day is
    await login(client, "zoe")
    assert (await client.post("/api/v1/household/switch", json={"user_id": str(lea)})).status_code == 200

    sitting = await _sitting(client, ids["Super Metroid"])
    base = f"/api/v1/retro/sittings/{sitting['id']}"
    beats = []
    for _ in range(15):
        clock.advance(timedelta(seconds=60))
        beats.append((await client.post(f"{base}/beat")).json())
    assert beats[0] == {"minutes_left": 14, "stop": False}
    assert beats[-1] == {"minutes_left": 0, "stop": True}  # spent: the page ends the game
    assert (await client.post(f"{base}/end")).status_code == 204
    await media.dispatch()  # the sitting becomes the profile's activity: its screen time of the day
    again = await client.post(f"/api/v1/retro/games/{ids['Super Metroid']}/sittings")
    assert again.status_code == 403 and again.json()["code"] == "household.screen_time_up"
    async with media.database.session() as session:
        played = await session.scalar(select(Sitting.user_id).where(Sitting.id == UUID(sitting["id"])))
    assert played == lea  # the profile's own sitting

    await households.change(owner, lea, restrictions=RestrictionSettings(types=["games"]))
    media.module.gate.forget()
    kept = await client.get(f"/api/v1/retro/games/{ids['Super Metroid']}")
    assert kept.status_code == 403  # its master keeps the games out


async def test_the_sweep_ends_a_silent_page_and_retells_the_library(
    app: FastAPI,
    client: httpx.AsyncClient,
    media: MediaHarness,
    retro: FakeRetro,
    retro_module: RetroModule,
    clock: FixedClock,
) -> None:
    await users(app, media, "zoe")
    ids = await _games(media)
    await login(client, "zoe")
    sitting = await _sitting(client, ids["Super Metroid"])
    clock.advance(timedelta(seconds=45))
    await client.post(f"/api/v1/retro/sittings/{sitting['id']}/beat")
    retro.refuse_sessions = True
    for _ in range(4):  # the page in the background (a phone locked): kept open, its time not counted
        clock.advance(timedelta(minutes=2))
        hidden = await client.post(f"/api/v1/retro/sittings/{sitting['id']}/beat", json={"active": False})
        assert hidden.status_code == 200
        assert await retro_module.service.sweep() == 0
    clock.advance(timedelta(minutes=4))
    assert await retro_module.service.sweep() == 0  # not silent for long enough yet
    clock.advance(timedelta(minutes=2))
    assert await retro_module.service.sweep() == 1  # the page went away
    assert retro.sessions == []  # the library was down
    retro.refuse_sessions = False
    assert await retro_module.service.sweep() == 0
    assert retro.sessions == [("r1", 45_000)]
    await retro_module.service.sweep()
    assert retro.sessions == [("r1", 45_000)]  # told once
    ended = (await media.events("media.playback_abandoned"))[-1][1]
    assert ended["watched_s"] == 45.0


async def test_switched_off_it_is_not_there(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    await users(app, media, "zoe")
    ids = await _games(media)
    await login(client, "zoe")

    async def off() -> bool:
        return False

    app.state.retro_module.enabled = off
    response = await client.get(f"/api/v1/retro/games/{ids['Super Metroid']}")
    assert response.status_code == 503 and response.json()["code"] == "retro.disabled"
