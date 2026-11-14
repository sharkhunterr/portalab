"""Retro play's routes (issue 419): whether a title plays here, a sitting (started, kept alive, ended),
and the files the play page loads — the game, its firmware, the emulator — relayed from the library."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Header, Path, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from portalab.capabilities.media import StreamBody
from portalab.modules.retro.api.deps import Module, Player
from portalab.modules.retro.service import HEARTBEAT_S, NotPlayable, Playable

router = APIRouter(prefix="/api/v1/retro", tags=["retro"])
PRIVATE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
# the emulator's files change with the library's version only: kept a day, in the member's browser only
EMULATOR = {"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"}
# the emulator's files are typed by the portal, never by the library (no page of another origin's making)
EMULATOR_TYPES = {
    "js": "text/javascript",
    "css": "text/css",
    "json": "application/json",
    "wasm": "application/wasm",
}
FILE = r"^[^/\\\x00]{1,400}$"
FIRMWARE = r"^[0-9A-Za-z_-]{1,64}$"
EMULATOR_PATH = r"^[A-Za-z0-9_-][A-Za-z0-9_./-]{0,199}$"  # no ``..`` either (checked below)


class RetroGameOut(BaseModel):
    title: str
    platform: str
    core: str
    threads: bool
    service_name: str | None = None


class FirmwareOut(BaseModel):
    id: str
    file_name: str
    verified: bool
    url: str


class SittingOut(BaseModel):
    id: UUID
    game: RetroGameOut
    game_url: str
    game_name: str
    firmware: list[FirmwareOut]
    emulator_path: str
    heartbeat_s: int


class BeatOut(BaseModel):
    minutes_left: int | None = None
    stop: bool = False


def _game(playable: Playable) -> RetroGameOut:
    return RetroGameOut(
        title=playable.game.title or playable.source.title,
        platform=playable.game.platform,
        core=playable.core,
        threads=playable.threads,
        service_name=playable.service_name,
    )


def _relay(
    body: StreamBody, stack: AsyncExitStack, headers: dict[str, str], media_type: str | None = None
) -> StreamingResponse:
    async def relay() -> AsyncIterator[bytes]:
        try:
            async for chunk in body.chunks:
                yield chunk
        finally:
            await stack.aclose()

    sent = dict(headers)
    if body.length is not None:
        sent["Content-Length"] = str(body.length)
    if body.content_range:
        sent["Content-Range"] = body.content_range
    return StreamingResponse(
        relay(), status_code=body.status, media_type=media_type or body.content_type, headers=sent
    )


def _file_name(name: str, multi: bool) -> str:
    """The name the emulator sees (its extension tells the format; a game of several files: an archive)."""
    base = name.replace("/", "_").replace("\\", "_")[:400] or "game"
    return f"{base}.zip" if multi and not base.lower().endswith(".zip") else base


@router.get("/games/{object_id}", response_model=RetroGameOut)
async def retro_game(principal: Player, module: Module, object_id: UUID) -> RetroGameOut:
    """Whether the title plays in the portal — its platform and emulator (404 ``retro.not_playable``)."""
    return _game(await module.service.game(principal, object_id))


@router.post("/games/{object_id}/sittings", response_model=SittingOut, status_code=status.HTTP_201_CREATED)
async def start_sitting(principal: Player, module: Module, object_id: UUID) -> SittingOut:
    started = await module.service.start(principal, object_id)
    playable, sitting = started.playable, started.sitting
    name = _file_name(playable.game.file_name, playable.game.multi)
    base = f"/api/v1/retro/sittings/{sitting}"
    return SittingOut(
        id=sitting,
        game=_game(playable),
        game_url=f"{base}/game/{quote(name, safe='')}",
        game_name=name,
        firmware=[
            FirmwareOut(
                id=f.id,
                file_name=f.file_name,
                verified=f.verified,
                url=f"{base}/firmware/{quote(f.id, safe='')}/{quote(f.file_name, safe='')}",
            )
            for f in started.firmware
        ],
        emulator_path=f"/api/v1/retro/libraries/{playable.source.service_id}/emulator/",
        heartbeat_s=HEARTBEAT_S,
    )


@router.post("/sittings/{sitting_id}/beat", response_model=BeatOut)
async def beat_sitting(principal: Player, module: Module, sitting_id: UUID) -> BeatOut:
    """The game still runs (sent every ``heartbeat_s`` while it does): a profile's screen time left today."""
    beat = await module.service.beat(principal, sitting_id)
    return BeatOut(minutes_left=beat.minutes_left, stop=beat.stop)


@router.post("/sittings/{sitting_id}/end", status_code=status.HTTP_204_NO_CONTENT)
async def end_sitting(principal: Player, module: Module, sitting_id: UUID) -> None:
    await module.service.end(principal, sitting_id)


@router.get("/sittings/{sitting_id}/game/{name}", include_in_schema=False)
async def sitting_game(
    principal: Player,
    module: Module,
    sitting_id: UUID,
    name: Annotated[str, Path(pattern=FILE)],
    range_header: Annotated[str | None, Header(alias="Range", max_length=100)] = None,
) -> StreamingResponse:
    """The game's file (or its files as one archive), to the sitting's player only, while it is open."""
    stack = AsyncExitStack()
    body, _ = await module.service.open_game(principal, sitting_id, range_header, stack)
    return _relay(
        body,
        stack,
        {**PRIVATE, "Accept-Ranges": "bytes", "Content-Disposition": "attachment"},
        "application/octet-stream",
    )


@router.head("/sittings/{sitting_id}/game/{name}", include_in_schema=False)
async def sitting_game_size(
    principal: Player, module: Module, sitting_id: UUID, name: Annotated[str, Path(pattern=FILE)]
) -> Response:
    """The emulator asks the game's size first: told from the library's record, nothing downloaded."""
    _, game = await module.service.sitting_game(principal, sitting_id)
    headers = {**PRIVATE, "Accept-Ranges": "bytes"}
    if game.size is not None and not game.multi:  # an archive made on the fly has no size before
        headers["Content-Length"] = str(game.size)
    return Response(status_code=200, media_type="application/octet-stream", headers=headers)


@router.head("/sittings/{sitting_id}/firmware/{firmware_id}/{name}", include_in_schema=False)
async def sitting_firmware_there(
    principal: Player,
    module: Module,
    sitting_id: UUID,
    firmware_id: Annotated[str, Path(pattern=FIRMWARE)],
    name: Annotated[str, Path(pattern=FILE)],
) -> Response:
    """The emulator asks whether the firmware is there first."""
    await module.service.sitting_firmware(principal, sitting_id, firmware_id)
    return Response(status_code=200, media_type="application/octet-stream", headers=PRIVATE)


@router.get("/sittings/{sitting_id}/firmware/{firmware_id}/{name}", include_in_schema=False)
async def sitting_firmware(
    principal: Player,
    module: Module,
    sitting_id: UUID,
    firmware_id: Annotated[str, Path(pattern=FIRMWARE)],
    name: Annotated[str, Path(pattern=FILE)],
) -> StreamingResponse:
    """A firmware (BIOS) of the game's platform, to the sitting's player only, while it is open."""
    stack = AsyncExitStack()
    body, _ = await module.service.open_firmware(principal, sitting_id, firmware_id, stack)
    return _relay(body, stack, {**PRIVATE, "Content-Disposition": "attachment"}, "application/octet-stream")


@router.get("/libraries/{service_id}/emulator/{path:path}", include_in_schema=False)
async def library_emulator(
    principal: Player,
    module: Module,
    service_id: UUID,
    path: Annotated[str, Path(pattern=EMULATOR_PATH)],
) -> StreamingResponse:
    """The library's emulator (EmulatorJS: its loader, its cores, its translations), the same for all."""
    if ".." in path:
        raise NotPlayable("No such emulator file.")
    stack = AsyncExitStack()
    body = await module.service.open_emulator(service_id, path, stack)
    kind = EMULATOR_TYPES.get(path.rsplit(".", 1)[-1].lower(), "application/octet-stream")
    return _relay(body, stack, EMULATOR, kind)
