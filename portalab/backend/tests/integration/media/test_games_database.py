"""#368 — with a game database (IGDB): a game franchise's page lists every game of it, those of the library
found by their IGDB id (RomM's) or their title, the others absent and leading to their sheet, with their
covers through the portal; a game's sheet tells it, its franchises linked when the library has some of
their games, and which library title it is when the library has it."""

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.isolation import IsolationPolicy, ProviderGuard
from portalab.capabilities.media import GAME_DATABASE, GameDatabase, GameDetails, GameFranchise, PersonCredit
from portalab.capabilities.media.testkit import library_record
from portalab.capabilities.search import ParsedQuery
from portalab.core.authz_port import Principal
from portalab.modules.connectors.breaker.breaker import CircuitBreaker
from portalab.modules.connectors.services.providers import guarded_provider
from portalab.modules.media.models import ExternalId, MediaObject
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

ZELDA = "The Legend of Zelda"


def _game(ref: str, title: str, year: int, cover: str | None = None) -> PersonCredit:
    return PersonCredit(tmdb_id=ref, kind="game", title=title, year=year, department="game", poster=cover)


class _Igdb:
    def __init__(self) -> None:
        self.asked: list[tuple[str, list[str]]] = []
        self.delay = 0.0  # how long a search takes

    async def franchise(self, name: str, known: Sequence[str]) -> GameFranchise | None:
        self.asked.append((name, list(known)))
        if name != ZELDA:
            return None
        return GameFranchise(
            ids={"igdb": "franchises:596"},
            name=ZELDA,
            games=[
                _game("1022", ZELDA, 1986, "co1uii"),
                _game("1025", "Zelda II: The Adventure of Link", 1987),
                _game("7346", "Breath of the Wild", 2017, "co3p2d"),
            ],
        )

    async def game(self, ref: str) -> GameDetails | None:
        if ref == "1025":
            return GameDetails(
                ref="1025",
                title="Zelda II: The Adventure of Link",
                summary="Link's second quest.",
                year=1987,
                cover="co2zii",
                images=["sc1", "ar2"],
                platforms=["NES", "Game Boy Advance"],
                developers=["Nintendo R&D4"],
                franchises=[ZELDA, "Unknown Saga"],
            )
        if ref == "7346":
            return GameDetails(ref="7346", title="The Legend of Zelda: Breath of the Wild")
        return None

    async def search(self, query: str, limit: int) -> Sequence[PersonCredit]:
        await asyncio.sleep(self.delay)
        return [_game("1025", "Zelda II: The Adventure of Link", 1987, "co2zii"), _game("7346", "BOTW", 2017)]

    async def image(self, ref: str, size: str) -> bytes:
        return b"\xff\xd8" + f"{size}:{ref}".encode()


async def _library(app: FastAPI, media: MediaHarness) -> tuple[_Igdb, str]:
    await users(app, media, "zoe")
    romm = media.service(3, "romm")
    media.library(romm)
    await media.module.library.upsert(
        [
            # found by its IGDB id (RomM keeps it), under the library's own title
            library_record("g1", kind="game", title="Zelda BOTW", series=ZELDA, platform="Switch"),
            # found by its title
            library_record("g2", kind="game", title="The Legend of Zelda", series=ZELDA, platform="NES"),
        ],
        romm,
    )
    async with media.database.unit_of_work() as uow:
        botw = (
            await uow.session.execute(select(MediaObject).where(MediaObject.title == "Zelda BOTW"))
        ).scalar_one()
        uow.session.add(ExternalId(scheme="igdb", value="7346", object_id=botw.id))
    igdb = _Igdb()
    service = media.service(11, "igdb")
    media.provide(
        GAME_DATABASE,
        service,
        guarded_provider(
            igdb,
            GameDatabase,
            capability=GAME_DATABASE,
            guard=ProviderGuard(source_system="test", policy=IsolationPolicy(max_retries=0)),
            breaker=CircuitBreaker(threshold=2, open_seconds=30),
            usable=lambda: True,
        ),
    )
    return igdb, str(service.service_id)


async def _id(media: MediaHarness, title: str) -> str:
    async with media.database.session() as session:
        found: Any = (
            await session.execute(select(MediaObject.id).where(MediaObject.title == title))
        ).scalar_one()
        return str(found)


async def test_a_franchise_s_games(app: FastAPI, client: httpx.AsyncClient, media: MediaHarness) -> None:
    igdb, service = await _library(app, media)
    await login(client, "zoe")
    page = (await client.get("/api/v1/media/collection", params={"ref": f"series:{ZELDA}"})).json()
    assert igdb.asked == [(ZELDA, ["7346"])]  # told apart by the library's own games
    assert [(p["title"], p["status"], p["object_id"]) for p in page["parts"]] == [
        (ZELDA, "available", await _id(media, ZELDA)),  # its title
        ("Zelda II: The Adventure of Link", "absent", None),
        ("Zelda BOTW", "available", await _id(media, "Zelda BOTW")),  # its IGDB id, the library's title
    ]
    absent = page["parts"][1]
    assert absent["route"] == f"/media/game?service={service}&ref=1025" and absent["cover"] is None
    cover = await client.get(page["parts"][0]["cover"])
    assert cover.status_code == 200 and cover.content == b"\xff\xd8cover:co1uii"


async def test_a_game_s_sheet(app: FastAPI, client: httpx.AsyncClient, media: MediaHarness) -> None:
    _, service = await _library(app, media)
    await login(client, "zoe")
    sheet = (await client.get("/api/v1/media/game", params={"service": service, "ref": "1025"})).json()
    assert sheet["title"] == "Zelda II: The Adventure of Link" and sheet["library"] is None
    assert sheet["platforms"] == ["NES", "Game Boy Advance"] and sheet["developers"] == ["Nintendo R&D4"]
    assert [(f["name"], f["route"] is not None) for f in sheet["franchises"]] == [
        (ZELDA, True),
        ("Unknown Saga", False),
    ]
    assert sheet["backdrop"].endswith("size=artwork") and len(sheet["images"]) == 2
    shot = await client.get(sheet["images"][0])
    assert shot.content == b"\xff\xd8screenshot:sc1"
    held = (await client.get("/api/v1/media/game", params={"service": service, "ref": "7346"})).json()
    assert held["library"] == await _id(media, "Zelda BOTW")  # the library has it: its page instead
    assert (
        await client.get("/api/v1/media/game", params={"service": service, "ref": "9"})
    ).status_code == 404
    elsewhere = await client.get("/api/v1/media/game", params={"service": str(UUID(int=0)), "ref": "1025"})
    assert elsewhere.status_code == 404
    bad = await client.get("/api/v1/media/game-images", params={"service": service, "ref": "../x"})
    assert bad.status_code == 422


async def test_games_to_ask_for_in_the_search(app: FastAPI, media: MediaHarness) -> None:
    """#373: a game the library lacks among the search's « ask for it » results, opening its sheet; one it
    has (by its IGDB id) left to the library's own results."""
    _, service = await _library(app, media)
    zoe = (await users(app, media, "leo"))["leo"]
    provider = media.module.search.provider("request")
    assert provider is not None
    query = ParsedQuery(text="zelda", normalized="zelda", terms=("zelda",))
    items = (await provider.search(query, Principal(user_id=zoe), None, limit=10, cursor=None)).items  # type: ignore[arg-type]
    assert [(i.title, i.url_ref) for i in items] == [
        ("Zelda II: The Adventure of Link (1987)", f"/media/game?service={service}&ref=1025")
    ]
    assert items[0].facets["cover"].endswith("ref=co2zii&size=cover")


async def test_a_slow_database_answers_the_next_keystroke(app: FastAPI, media: MediaHarness) -> None:
    """#373: a game database slower than the search's budget does not hold the search: its answer, kept,
    comes with the next search of the same words."""
    igdb, _ = await _library(app, media)
    igdb.delay = 1.3
    leo = (await users(app, media, "leo"))["leo"]
    provider = media.module.search.provider("request")
    assert provider is not None
    query = ParsedQuery(text="zelda", normalized="zelda", terms=("zelda",))
    first = (await provider.search(query, Principal(user_id=leo), None, limit=10, cursor=None)).items  # type: ignore[arg-type]
    assert first == []
    await asyncio.sleep(0.5)  # the answer arrives meanwhile
    again = (await provider.search(query, Principal(user_id=leo), None, limit=10, cursor=None)).items  # type: ignore[arg-type]
    assert [i.title for i in again] == ["Zelda II: The Adventure of Link (1987)"]
