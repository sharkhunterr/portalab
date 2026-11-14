"""Issue 421 — the engines and controls: a Flash game plays in Ruffle (as RomM serves it), a Sega console's
game gets its virtual gamepad, the cores are RomM's own; each member's emulator settings (controls, options)
are kept per core and follow them from device to device — a household profile's are its own."""

from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.capabilities.retro import RetroGame
from portalab.core.authz_port import Principal
from portalab.modules.media.models import MediaObject
from portalab.modules.retro.cores import core_for
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.retro.conftest import FakeRetro


async def _more(media: MediaHarness, retro: FakeRetro) -> dict[str, UUID]:
    retro.games["f1"] = RetroGame("f1", "Alien Hominid", "flash", "40", "alien.swf")
    retro.games["s1"] = RetroGame("s1", "Sonic", "genesis", "41", "sonic.md")
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record("f1", kind="game", title="Alien Hominid"),
            library_record("s1", kind="game", title="Sonic"),
        ],
        one,
    )
    async with media.database.session() as session:
        return {t: i for t, i in (await session.execute(select(MediaObject.title, MediaObject.id))).all()}


def test_the_cores_are_romms() -> None:
    assert core_for("snes") == "snes9x" and core_for("C128") == "vice_x128" and core_for("flash") == "ruffle"
    assert core_for("3ds") is None  # only behind RomM's netplay switch
    assert core_for("magnavox") is None


async def test_flash_plays_in_ruffle_and_sega_gets_its_gamepad(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    await users(app, media, "zoe")
    ids = await _more(media, retro)
    await login(client, "zoe")
    flash = (await client.get(f"/api/v1/retro/games/{ids['Alien Hominid']}")).json()
    assert (flash["engine"], flash["core"], flash["control_scheme"]) == ("ruffle", "ruffle", None)
    sitting = (await client.post(f"/api/v1/retro/games/{ids['Alien Hominid']}/sittings")).json()
    assert sitting["emulator_path"].endswith("/emulator/ruffle/")
    loader = await client.get(f"{sitting['emulator_path']}ruffle.js")
    assert loader.status_code == 200 and loader.headers["content-type"].startswith("text/javascript")
    assert retro.opened[-1] == ("emulator", "", "ruffle/ruffle.js", None)
    sonic = (await client.get(f"/api/v1/retro/games/{ids['Sonic']}")).json()
    assert (sonic["engine"], sonic["core"], sonic["control_scheme"]) == (
        "emulatorjs",
        "genesis_plus_gx",
        "segaMD",
    )


async def test_settings_follow_the_member(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    people = await users(app, media, "zoe")
    await login(client, "zoe")
    assert (await client.get("/api/v1/retro/preferences/snes9x")).json() == {"data": None}
    controls = {
        "controlSettings": {"0": {"0": {"value": "x", "value2": "BUTTON_2"}}},
        "settings": {"shader": "crt"},
    }
    assert (await client.put("/api/v1/retro/preferences/snes9x", json={"data": controls})).status_code == 204
    assert (await client.get("/api/v1/retro/preferences/snes9x")).json() == {"data": controls}
    assert (await client.get("/api/v1/retro/preferences/mgba")).json() == {"data": None}  # per core
    huge = {"x": "a" * 70_000}
    assert (await client.put("/api/v1/retro/preferences/snes9x", json={"data": huge})).status_code == 400
    assert (await client.get("/api/v1/retro/preferences/Bad..Core")).status_code == 422

    households = app.state.household_module.service
    created = await households.create(
        Principal(user_id=people["zoe"]), display_name="Léa", kind="standard", color=None, pin=None
    )
    await client.post("/api/v1/household/switch", json={"user_id": str(created["id"])})
    assert (await client.get("/api/v1/retro/preferences/snes9x")).json() == {
        "data": None
    }  # the profile's own
