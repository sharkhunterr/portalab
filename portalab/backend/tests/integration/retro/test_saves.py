"""Issue 420 — a member's saves and save states, kept by the portal per member and per household profile:
the game's own save written as the emulator writes it and loaded when it starts again, states in slots with
the screen's picture, « Continue » from the latest one; each copied to the library, labelled with whose it is
(its account is shared), replaced in place, deleted with it, retried when the library did not answer."""

from uuid import UUID

import httpx
from fastapi import FastAPI

from portalab.core.authz_port import Principal
from portalab.modules.retro.module import RetroModule
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.retro.conftest import FakeRetro
from tests.integration.retro.test_retro import _games, _sitting

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


async def test_a_members_saves_and_states(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    await users(app, media, "zoe")
    ids = await _games(media)
    await login(client, "zoe")
    sitting = await _sitting(client, ids["Super Metroid"])
    saves = sitting["saves_path"]
    assert sitting["state_url"] is None
    assert (await client.get(f"{saves}sram")).status_code == 404  # nothing saved yet

    assert (await client.put(f"{saves}sram", content=b"SRAM-1")).status_code == 204
    assert (await client.get(f"{saves}sram")).content == b"SRAM-1"
    state = await client.put(f"{saves}states/1", content=b"STATE-1")
    assert state.status_code == 200 and state.json()["slot"] == 1 and state.json()["size"] == 7
    assert (await client.put(f"{saves}states/1/picture", content=PNG)).status_code == 204
    picture = await client.get(f"{saves}states/1/picture")
    assert picture.headers["content-type"] == "image/png" and picture.content == PNG
    # the game's page shows it too, to choose where to resume (no sitting needed)
    shown = await client.get(f"/api/v1/retro/games/{ids['Super Metroid']}/states/1/picture")
    assert shown.status_code == 200 and shown.content == PNG
    assert (
        await client.get(f"/api/v1/retro/games/{ids['Super Metroid']}/states/3/picture")
    ).status_code == 404

    progress = (await client.get(f"{saves}saves")).json()
    assert progress["sram_at"] is not None and progress["latest_slot"] == 1 and progress["slots"] == 5
    assert [(s["slot"], s["has_picture"]) for s in progress["states"]] == [(1, True)]

    sram, first, pictured = retro.copies
    assert (sram["kind"], sram["rom"], sram["core"], sram["data"]) == ("save", "r1", "snes9x", b"SRAM-1")
    assert sram["name"].endswith("-r1.srm") and sram["labels"][0] == "Portalab" and len(sram["labels"]) == 2
    assert (first["kind"], first["name"][-12:], first["picture"]) == ("state", ".slot1.state", None)
    assert pictured["picture"] == PNG and pictured["replaces"] == "102"  # replaced in place

    await client.put(f"{saves}states/1", content=b"STATE-2")
    assert retro.copies[-1]["replaces"] == "102" and retro.copies[-1]["data"] == b"STATE-2"
    assert (await client.get(f"{saves}states/1/picture")).status_code == 404  # a new state: a new picture

    game = (await client.get(f"/api/v1/retro/games/{ids['Super Metroid']}")).json()
    assert game["progress"]["latest_slot"] == 1
    again = await client.post(f"/api/v1/retro/games/{ids['Super Metroid']}/sittings", json={"resume": 1})
    assert again.json()["state_url"].endswith("/states/1")
    absent = await client.post(f"/api/v1/retro/games/{ids['Super Metroid']}/sittings", json={"resume": 3})
    assert absent.json()["state_url"] is None  # nothing there: a new game
    resumed = again.json()["saves_path"]
    assert (await client.get(f"{resumed}states/1")).content == b"STATE-2"

    assert (await client.delete(f"{resumed}states/1")).status_code == 204
    assert retro.deleted == [("state", "102")]
    assert (await client.get(f"{resumed}states/1")).status_code == 404


async def test_what_is_refused(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    await users(app, media, "zoe", "max")
    ids = await _games(media)
    await login(client, "zoe")
    saves = (await _sitting(client, ids["Super Metroid"]))["saves_path"]
    assert (await client.put(f"{saves}sram", content=b"")).json()["code"] == "retro.save_refused"
    assert (await client.put(f"{saves}states/9", content=b"x")).status_code == 422
    await client.put(f"{saves}states/2", content=b"STATE")
    refused = await client.put(f"{saves}states/2/picture", content=b"<svg onload=alert(1)>")
    assert refused.status_code == 400  # a picture the portal keeps, nothing else
    assert (await client.put(f"{saves}states/4/picture", content=PNG)).status_code == 404

    await client.put(f"{saves}states/2/picture", content=PNG)
    await login(client, "max")  # another member: neither reads nor writes them, nor sees their pictures
    assert (
        await client.get(f"/api/v1/retro/games/{ids['Super Metroid']}/states/2/picture")
    ).status_code == 404
    for method in ("GET", "PUT"):
        response = await client.request(method, f"{saves}states/2", content=b"x")
        assert response.status_code == 404, method


async def test_a_profile_keeps_its_own(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    people = await users(app, media, "zoe")
    ids = await _games(media)
    households = app.state.household_module.service
    owner = Principal(user_id=people["zoe"])
    created = await households.create(owner, display_name="Léa", kind="standard", color=None, pin=None)
    lea = UUID(str(created["id"]))
    await login(client, "zoe")
    master = (await _sitting(client, ids["Super Metroid"]))["saves_path"]
    await client.put(f"{master}states/1", content=b"MASTER")

    assert (await client.post("/api/v1/household/switch", json={"user_id": str(lea)})).status_code == 200
    game = (await client.get(f"/api/v1/retro/games/{ids['Super Metroid']}")).json()
    assert game["progress"]["states"] == []  # the master's are not the profile's
    own = (await _sitting(client, ids["Super Metroid"]))["saves_path"]
    assert (await client.get(f"{own}states/1")).status_code == 404
    await client.put(f"{own}states/1", content=b"LEA")
    assert retro.copies[-1]["labels"] == ["Portalab", "Léa"]  # labelled with the profile in the library
    assert retro.copies[-1]["name"] != retro.copies[0]["name"]  # never the master's copy


async def test_a_library_down_gets_them_later(
    app: FastAPI,
    client: httpx.AsyncClient,
    media: MediaHarness,
    retro: FakeRetro,
    retro_module: RetroModule,
) -> None:
    await users(app, media, "zoe")
    ids = await _games(media)
    await login(client, "zoe")
    saves = (await _sitting(client, ids["Super Metroid"]))["saves_path"]
    retro.refuse_copies = True
    assert (await client.put(f"{saves}sram", content=b"SRAM")).status_code == 204  # kept anyway
    assert retro.copies == []
    retro.refuse_copies = False
    assert await retro_module.saves.sync() == 1
    assert [c["data"] for c in retro.copies] == [b"SRAM"]
    assert await retro_module.saves.sync() == 0  # copied once
