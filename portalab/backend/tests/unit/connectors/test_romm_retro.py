"""Issue 419 — RomM's ``media.retro_source``: a game's platform and file, its platform's firmware, the game,
firmware and EmulatorJS files relayed as RomM sends them (the game and the firmware with the account's
credentials, the emulator's public files without), a play session told to RomM as the portal's device — and
the portal's sessions left out of the account's history read back (the portal counted them already)."""

import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from portalab.capabilities.connector_http import ConnectorHttpClient
from portalab.capabilities.connector_sdk import ServiceHandle
from portalab.capabilities.media import ACTIVITY_HISTORY
from portalab.capabilities.results import ProviderNotFound
from portalab.capabilities.retro import RETRO_SOURCE, RetroSource
from portalab.connectors.romm import RommConnector, game_rating

ROM = {
    "id": 12,
    "name": "Super Metroid",
    "fs_name": "Super Metroid (E).sfc",
    "platform_slug": "SNES",
    "platform_id": 3,
    "fs_size_bytes": 3_145_728,
    "has_multiple_files": False,
    "missing_from_fs": False,
}


class _Server:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/api/roms/12":
            return httpx.Response(200, json=ROM)
        if path == "/api/roms/13":
            return httpx.Response(200, json={**ROM, "id": 13, "missing_from_fs": True})
        if path == "/api/firmware":
            assert request.url.params["platform_id"] == "3"
            return httpx.Response(
                200, json=[{"id": 5, "file_name": "bios.bin", "is_verified": True}, {"x": 1}]
            )
        if path == "/api/roms/12/content/Super Metroid (E).sfc":
            assert request.url.raw_path.startswith(b"/api/roms/12/content/Super%20Metroid%20%28E%29.sfc?")
            assert request.headers["authorization"].startswith("Basic ")
            assert request.url.params["purpose"] == "play"
            return httpx.Response(206, content=b"ROM", headers={"content-range": "bytes 0-2/9"})
        if path == "/api/firmware/5/content/bios.bin":
            return httpx.Response(200, content=b"BIOS")
        if path == "/assets/emulatorjs/data/cores/snes9x-wasm.data":
            assert "authorization" not in request.headers  # RomM serves its emulator to anyone
            return httpx.Response(200, content=b"CORE", headers={"content-type": "application/octet-stream"})
        if path == "/api/devices" and request.method == "POST":
            return httpx.Response(200, json={"device_id": "dev-1", "name": "Portalab", "created_at": "x"})
        if path == "/api/devices":
            return httpx.Response(200, json=[{"id": "dev-1", "client": "portalab"}, {"id": "dev-2"}])
        if path == "/api/play-sessions" and request.method == "POST":
            return httpx.Response(200, json={"results": [], "created_count": 1, "skipped_count": 0})
        if path == "/api/states" and request.method == "POST":
            assert request.url.params["rom_id"] == "12" and request.url.params["emulator"] == "snes9x"
            assert b'name="stateFile"; filename="me.state"' in request.content
            return httpx.Response(200, json={"id": 77})
        if path == "/api/states/77" and request.method == "PUT":
            return httpx.Response(200, json={"id": 77})
        if path == "/api/states/66" and request.method == "PUT":
            return httpx.Response(404, json={"detail": "gone"})
        if path == "/api/states/77/labels":
            return httpx.Response(200, json={"id": 77})
        if path == "/api/saves/delete":
            return httpx.Response(200, json={"successful_items": 1})
        if path == "/api/users/me":
            return httpx.Response(200, json={"id": 1, "username": "portal"})
        if path == "/api/roms":
            return httpx.Response(200, json={"items": [], "total": 0})
        if path == "/api/play-sessions":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "rom_id": 12,
                        "device_id": "dev-1",
                        "start_time": "2026-11-14T10:00:00Z",
                        "end_time": "2026-11-14T10:30:00Z",
                        "duration_ms": 1_800_000,
                    },
                    {
                        "id": 2,
                        "rom_id": 12,
                        "device_id": None,
                        "start_time": "2026-11-14T11:00:00Z",
                        "end_time": "2026-11-14T11:10:00Z",
                        "duration_ms": 600_000,
                    },
                ],
            )
        return httpx.Response(404)


@pytest.fixture
def server() -> _Server:
    return _Server()


def _provider(server: _Server, capability: str = RETRO_SOURCE):  # type: ignore[no-untyped-def]
    http = ConnectorHttpClient("http://romm.lan", transport=httpx.MockTransport(server), retries=0)
    handle = ServiceHandle(
        service_id=UUID(int=9),
        name="RomM",
        config={"username": "portal"},
        secrets={"password": "x"},
        http=http,
    )
    return RommConnector().provider(capability, handle)


async def test_a_game_its_firmware_and_its_files(server: _Server) -> None:
    retro = _provider(server)
    assert isinstance(retro, RetroSource)
    game = await retro.game("12")
    assert game is not None
    assert (game.platform, game.platform_id, game.file_name, game.size, game.multi, game.present) == (
        "snes",
        "3",
        "Super Metroid (E).sfc",
        3_145_728,
        False,
        True,
    )
    missing = await retro.game("13")
    assert missing is not None and not missing.present
    assert [(f.id, f.file_name, f.verified) for f in await retro.firmware("3")] == [("5", "bios.bin", True)]
    assert await retro.firmware("../x") == []

    async with retro.open("rom", "12", game.file_name, "bytes=0-2") as body:
        assert (body.status, body.content_range) == (206, "bytes 0-2/9")
        assert b"".join([c async for c in body.chunks]) == b"ROM"
    assert server.requests[-1].headers["range"] == "bytes=0-2"
    async with retro.open("firmware", "5", "bios.bin") as body:
        assert b"".join([c async for c in body.chunks]) == b"BIOS"
    async with retro.open("emulator", "", "cores/snes9x-wasm.data") as body:
        assert b"".join([c async for c in body.chunks]) == b"CORE"


async def test_names_that_would_leave_their_folder_are_refused(server: _Server) -> None:
    retro = _provider(server)
    for kind, name in (("emulator", "../secret"), ("emulator", "/etc/passwd"), ("rom", "a/b"), ("rom", "")):
        with pytest.raises(ProviderNotFound):
            async with retro.open(kind, "12", name):
                pass
    with pytest.raises(ProviderNotFound):  # RomM's 404 (a missing translation)
        async with retro.open("emulator", "", "localization/fr-FR.json"):
            pass


async def test_a_session_goes_to_romm_as_the_portals_device(server: _Server) -> None:
    retro = _provider(server)
    start = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
    await retro.record_session("12", start, datetime(2026, 11, 14, 10, 5, tzinfo=UTC), 300_000)
    sent = [r for r in server.requests if r.url.path == "/api/play-sessions" and r.method == "POST"]
    assert json.loads(sent[0].content) == {
        "device_id": "dev-1",
        "sessions": [
            {
                "rom_id": 12,
                "start_time": "2026-11-14T10:00:00+00:00",
                "end_time": "2026-11-14T10:05:00+00:00",
                "duration_ms": 300_000,
            }
        ],
    }
    device = [r for r in server.requests if r.url.path == "/api/devices" and r.method == "POST"]
    assert json.loads(device[0].content)["client"] == "portalab"
    await retro.record_session("not-a-rom", start, start, 1)  # never sent
    assert len([r for r in server.requests if r.url.path == "/api/play-sessions"]) == 1


async def test_the_history_leaves_out_the_portals_sessions(server: _Server) -> None:
    page = await _provider(server, ACTIVITY_HISTORY).history(since=None, cursor=None)
    assert [(item.ref, item.watched_s) for item in page.items] == [("session:2", 600.0)]


async def test_saves_and_states_copied_and_labelled(server: _Server) -> None:
    retro = _provider(server)
    made = await retro.put_file("state", "12", "snes9x", "me.state", b"S", b"\x89PNG", ["Portalab", "Léa"])
    assert made == "77"
    sent = next(r for r in server.requests if r.url.path == "/api/states")
    assert b'name="screenshotFile"' in sent.content
    labels = [r for r in server.requests if r.url.path == "/api/states/77/labels"][-1]
    assert json.loads(labels.content) == {"labels": ["Portalab", "Léa"]}
    assert await retro.put_file("state", "12", "snes9x", "me.state", b"S2", None, ["Portalab"], "77") == "77"
    assert server.requests[-2].method == "PUT" and server.requests[-2].url.path == "/api/states/77"
    # RomM lost the copy to replace: a new one
    assert await retro.put_file("state", "12", "snes9x", "me.state", b"S3", None, ["Portalab"], "66") == "77"
    await retro.delete_file("save", "5")
    assert json.loads(server.requests[-1].content) == {"saves": [5]}
    await retro.delete_file("state", "not-an-id")  # never sent
    assert server.requests[-1].url.path == "/api/saves/delete"


def test_a_games_strictest_rating() -> None:
    """Issue 421: the strictest of IGDB's ratings RomM keeps for a game; bare and pending ones say nothing."""
    rated = {
        "igdb_metadata": {
            "age_ratings": [
                {"category": "PEGI", "rating": "Seven", "rating_cover_url": ""},
                {"category": "ESRB", "rating": "T", "rating_cover_url": ""},
                {"category": "ESRB", "rating": "RP", "rating_cover_url": ""},
            ]
        },
        "metadatum": {"age_ratings": ["M"]},
    }
    assert game_rating(rated) == "ESRB T"
    assert (
        game_rating({"igdb_metadata": {"age_ratings": [{"category": "PEGI", "rating": "Eighteen"}]}})
        == "PEGI 18"
    )
    assert game_rating({"metadatum": {"age_ratings": ["M"]}}) is None
    assert game_rating({"name": "Pong"}) is None
