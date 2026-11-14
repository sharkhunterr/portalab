"""Issue 420 — one game, several copies in the library (regions, revisions): the game's page lists every copy
played here with its own progress, a new game starts the copy chosen, and each copy keeps its own saves."""

from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.media.testkit import library_record
from portalab.capabilities.retro import RetroGame
from portalab.modules.media.models import MediaObject
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users
from tests.integration.retro.conftest import FakeRetro

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


async def _tintin(media: MediaHarness, retro: FakeRetro) -> UUID:
    retro.games["t1"] = RetroGame("t1", "Tintin in Tibet", "gb", "9", "tintin (E).gb", variant="Europe")
    retro.games["t2"] = RetroGame(
        "t2", "Tintin in Tibet", "gb", "9", "tintin (E,NL).gb", variant="Europe, Netherlands"
    )
    one = media.service(1)
    media.library(one)
    await media.module.library.upsert(
        [
            library_record("t1", kind="game", title="Tintin in Tibet", year=1995, ids={"igdb": "77"}),
            library_record("t2", kind="game", title="Tintin in Tibet", year=1995, ids={"igdb": "77"}),
        ],
        one,
    )
    async with media.database.session() as session:
        found = await session.scalar(select(MediaObject.id).where(MediaObject.title == "Tintin in Tibet"))
    assert found is not None
    return found


async def test_each_copy_is_chosen_and_keeps_its_saves(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, retro: FakeRetro
) -> None:
    await users(app, media, "zoe")
    tintin = await _tintin(media, retro)
    await login(client, "zoe")
    game = (await client.get(f"/api/v1/retro/games/{tintin}")).json()
    assert sorted((r["id"], r["variant"]) for r in game["roms"]) == [
        ("t1", "Europe"),
        ("t2", "Europe, Netherlands"),
    ]

    sitting = await client.post(f"/api/v1/retro/games/{tintin}/sittings", json={"rom": "t2"})
    assert sitting.status_code == 201 and sitting.json()["game"]["rom"] == "t2"
    saves = sitting.json()["saves_path"]
    await client.put(f"{saves}states/1", content=b"NL")
    await client.put(f"{saves}states/1/picture", content=PNG)
    game = (await client.get(f"/api/v1/retro/games/{tintin}")).json()
    progress = {r["id"]: [s["slot"] for s in r["progress"]["states"]] for r in game["roms"]}
    assert progress == {"t1": [], "t2": [1]}  # the other copy's saves are not this one's
    picture = await client.get(f"/api/v1/retro/games/{tintin}/states/1/picture", params={"rom": "t2"})
    assert picture.status_code == 200 and picture.content == PNG
    other = await client.get(f"/api/v1/retro/games/{tintin}/states/1/picture", params={"rom": "t1"})
    assert other.status_code == 404

    resumed = await client.post(f"/api/v1/retro/games/{tintin}/sittings", json={"rom": "t2", "resume": 1})
    assert resumed.json()["state_url"].endswith("/states/1")
    elsewhere = await client.post(f"/api/v1/retro/games/{tintin}/sittings", json={"rom": "t1", "resume": 1})
    assert elsewhere.json()["state_url"] is None  # nothing saved in that copy: a new game
    unknown = await client.post(f"/api/v1/retro/games/{tintin}/sittings", json={"rom": "t9"})
    assert unknown.status_code == 404 and unknown.json()["code"] == "retro.not_playable"
