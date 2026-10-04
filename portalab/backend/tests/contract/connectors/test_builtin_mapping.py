"""What the shipped connectors produce from each API: kinds, parents, external ids, availability, paging,
playback, requests — and that image references can never reach another host or leak a secret."""

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.media import LIBRARY, PLAYBACK, REQUESTS, LibraryPayload, RequestPayload
from portalab.capabilities.results import InvalidPayload
from portalab.connectors.arr import RadarrConnector, SonarrConnector
from portalab.connectors.builtin import builtin_connectors, register_builtin
from portalab.connectors.http_base import parse_time, safe_id
from portalab.connectors.jellyfin import JellyfinConnector
from portalab.connectors.plex import PlexConnector
from portalab.connectors.romm import RommConnector, cover_path
from portalab.connectors.seerr import SeerrConnector
from tests.contract.connectors.builtin_fixtures import ROUTES, SEERR, handle_for


class _Ctx:
    def __init__(self, service: Any, capability: str) -> None:
        self.service, self.capability, self.kind = service, capability, "manual"


async def records(connector: Any, key: str, capability: str = LIBRARY, **kw: Any) -> list[SourceRecord]:
    handle = handle_for(key, **kw)
    return [r async for r in connector.sync(_Ctx(handle, capability), None) if isinstance(r, SourceRecord)]


async def test_jellyfin_library() -> None:
    seen: list[httpx.Request] = []
    found = await records(JellyfinConnector(), "jellyfin", seen=seen)
    by_id = {r.external_id: r for r in found}
    assert [r.kind for r in found] == ["movie", "series", "season", "episode"]  # folders are skipped
    dune = LibraryPayload.model_validate(dict(by_id["m1"].payload))
    assert dune.ids == {"tmdb": "438631", "imdb": "tt1160419"} and dune.duration_s == 9360.0
    assert dune.image == "m1" and by_id["m1"].observed_at == datetime(2024, 1, 2, 3, 4, 5, 123456, UTC)
    assert by_id["se1"].payload["parent"] == "s1" and by_id["e1"].payload["parent"] == "se1"
    assert 'Token="jf-secret-key"' in seen[0].headers["authorization"]


async def test_jellyfin_playback() -> None:
    playback = JellyfinConnector().provider(PLAYBACK, handle_for("jellyfin"))
    sessions = await playback.now_playing()
    assert len(sessions) == 1 and sessions[0].position_s == 60.0 and sessions[0].device == "TV"


async def test_plex_pages_and_ids() -> None:
    found = await records(PlexConnector(), "plex")
    assert [r.external_id for r in found] == ["101", "102", "103"]  # three items over two pages
    assert found[0].payload["ids"] == {"tmdb": "438631"} and found[0].payload["image"] == "101"
    assert "image" not in found[1].payload
    sessions = await PlexConnector().provider(PLAYBACK, handle_for("plex")).now_playing()
    assert sessions[0].state == "paused" and sessions[0].external_user_id == "1"


async def test_arr_availability_and_seasons() -> None:
    movies = await records(RadarrConnector(), "radarr")
    assert [(r.external_id, r.payload["available"]) for r in movies] == [
        ("movie:1", True),
        ("movie:2", False),
    ]
    assert movies[0].payload["duration_s"] == 156 * 60
    series = await records(SonarrConnector(), "sonarr")
    assert [(r.external_id, r.kind) for r in series] == [
        ("series:5", "series"),
        ("season:5:0", "season"),
        ("season:5:1", "season"),
    ]
    assert series[1].payload["available"] is False and series[2].payload["parent"] == "series:5"


async def test_arr_refuses_the_other_app() -> None:
    result = await SonarrConnector().test_connection(
        handle_for("sonarr", routes={"/api/v3/system/status": {"appName": "Radarr", "version": "5"}})
    )
    assert not result.ok and not result.compatible and "not Sonarr" in result.detail


async def test_seerr_requests_and_submit() -> None:
    found = await records(SeerrConnector(), "seerr", capability=REQUESTS)
    first, second = (RequestPayload.model_validate(dict(r.payload)) for r in found)
    assert (first.title, first.kind, first.state, first.requester) == ("Dune", "movie", "available", "3")
    assert (second.title, second.kind, second.state) == ("Andor", "series", "pending")

    seen: list[httpx.Request] = []
    routes = {**SEERR, "/api/v1/request": {"id": 99, "status": 1, "media": {"status": 2}}}
    requests = SeerrConnector().provider(REQUESTS, handle_for("seerr", routes=routes, seen=seen))
    made = await requests.submit({"tmdb": "83867"}, "series", "Andor", "3")
    assert made.external_request_id == "99" and made.state == "pending"
    assert json.loads(seen[-1].content) == {
        "mediaType": "tv",
        "mediaId": 83867,
        "seasons": "all",
        "userId": 3,
    }
    with pytest.raises(InvalidPayload):
        await requests.submit({"imdb": "tt1"}, "movie", "?", None)


async def test_romm_both_page_shapes() -> None:
    found = await records(RommConnector(), "romm")
    assert [r.payload["title"] for r in found] == ["Super Metroid", "Unknown Game"]
    assert found[0].payload["genres"] == ["SNES"] and found[0].payload["year"] == 1994
    assert found[0].payload["image"] == "roms/2/1/cover/big.png"
    legacy = {**ROUTES["romm"], "/api/roms": ROUTES["romm"]["/api/roms"]["items"]}  # RomM 3: a bare list
    assert len(await records(RommConnector(), "romm", routes=legacy)) == 2


def test_image_refs_cannot_escape_the_service() -> None:
    assert cover_path("roms/2/1/cover/big.png") == "/assets/romm/resources/roms/2/1/cover/big.png"
    for bad in ("../../etc/passwd", "http://evil.example/x", "roms/../../x", "//evil/x?a"):
        with pytest.raises(InvalidPayload):
            cover_path(bad)
    for bad in ("../x", "http://evil", "a/b", "x" * 65):
        with pytest.raises(InvalidPayload):
            safe_id(bad)


async def test_images_go_through_the_service() -> None:
    seen: list[httpx.Request] = []
    library = JellyfinConnector().provider(LIBRARY, handle_for("jellyfin", seen=seen))
    assert await library.fetch_image("m1") == b"\x89PNG-image"
    assert seen[-1].url.path == "/Items/m1/Images/Primary" and seen[-1].url.host.startswith("jellyfin-")
    with pytest.raises(InvalidPayload):
        await library.fetch_image("http://evil.example/x")


def test_parse_time_formats() -> None:
    assert parse_time("2024-01-02T03:04:05Z") == datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert parse_time(1_700_000_000) == datetime.fromtimestamp(1_700_000_000, UTC)
    assert parse_time(763_084_800_000) == datetime(1994, 3, 8, tzinfo=UTC)
    assert parse_time("not a date") is None and parse_time(None) is None


def test_builtin_catalog_registers_once() -> None:
    from portalab.capabilities.connector_sdk import ConnectorRegistry as Registry

    registry = Registry()
    register_builtin(registry)
    register_builtin(registry)  # idempotent at start-up
    assert sorted(c.key for c in registry.all()) == sorted(c.key for c in builtin_connectors())
    assert {c.key for c in registry.all()} == {
        "jellyfin",
        "plex",
        "seerr",
        "radarr",
        "sonarr",
        "romm",
        "tautulli",
        "grimmory",
        "tmdb",
    }
