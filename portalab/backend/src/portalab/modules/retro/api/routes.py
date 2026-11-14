"""Retro play's routes (issue 419): whether a title plays here, a sitting (started, kept alive, ended),
and the files the play page loads — the game, its firmware, the emulator — relayed from the library; issue
420: the player's saves and save states (kept by the portal, copied to the library)."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Header, Path, Request, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from portalab.capabilities.media import StreamBody
from portalab.modules.retro.accounts import AccountState
from portalab.modules.retro.api.deps import Module, Player
from portalab.modules.retro.saves import SLOTS, Progress, StateInfo
from portalab.modules.retro.service import HEARTBEAT_S, NotPlayable, Playable, player_of

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


class RetroStateOut(BaseModel):
    slot: int
    size: int
    updated_at: datetime
    has_picture: bool


class RetroProgressOut(BaseModel):
    """420: the player's progress in the game — its own save, its save states (slot 0: where it was left)."""

    sram_at: datetime | None
    states: list[RetroStateOut]
    latest_slot: int | None
    slots: int


class RetroGameOut(BaseModel):
    title: str
    platform: str
    core: str
    threads: bool
    service_name: str | None = None
    progress: RetroProgressOut | None = None
    engine: Literal["emulatorjs", "ruffle"] = "emulatorjs"  # 421
    control_scheme: str | None = None  # 421: the virtual gamepad of a Sega console


class SittingIn(BaseModel):
    resume: int | None = Field(default=None, ge=0, le=SLOTS)  # 420: the save state to start from


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
    saves_path: str  # 420: ``sram``, ``states/{slot}`` (and ``/picture``) under it
    state_url: str | None = None  # the state the game starts from (« Continue »)


class BeatOut(BaseModel):
    minutes_left: int | None = None
    stop: bool = False


def _state(state: StateInfo) -> RetroStateOut:
    return RetroStateOut(
        slot=state.slot, size=state.size, updated_at=state.updated_at, has_picture=state.has_picture
    )


def _progress(progress: Progress) -> RetroProgressOut:
    latest = progress.latest
    return RetroProgressOut(
        sram_at=progress.sram_at,
        states=[_state(s) for s in progress.states],
        latest_slot=latest.slot if latest is not None else None,
        slots=SLOTS,
    )


def _game(playable: Playable, progress: Progress | None = None) -> RetroGameOut:
    return RetroGameOut(
        title=playable.game.title or playable.source.title,
        platform=playable.game.platform,
        core=playable.core,
        threads=playable.threads,
        service_name=playable.service_name,
        progress=_progress(progress) if progress is not None else None,
        engine="ruffle" if playable.engine == "ruffle" else "emulatorjs",
        control_scheme=playable.control_scheme,
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
    """Whether the title plays in the portal — its platform and emulator (404 ``retro.not_playable``) — and
    the player's progress in it."""
    playable = await module.service.game(principal, object_id)
    progress = await module.saves.progress(
        player_of(principal), playable.source.service_id, playable.game.external_id
    )
    return _game(playable, progress)


@router.post("/games/{object_id}/sittings", response_model=SittingOut, status_code=status.HTTP_201_CREATED)
async def start_sitting(
    principal: Player, module: Module, object_id: UUID, body: SittingIn | None = None
) -> SittingOut:
    started = await module.service.start(principal, object_id)
    playable, sitting = started.playable, started.sitting
    progress = await module.saves.progress(
        player_of(principal), playable.source.service_id, playable.game.external_id
    )
    resume = body.resume if body is not None else None
    if resume is not None and all(s.slot != resume for s in progress.states):
        resume = None  # nothing there (deleted meanwhile): a new game
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
        emulator_path=f"/api/v1/retro/libraries/{playable.source.service_id}/emulator/"
        + ("ruffle/" if playable.engine == "ruffle" else ""),
        heartbeat_s=HEARTBEAT_S,
        saves_path=f"{base}/",
        state_url=f"{base}/states/{resume}" if resume is not None else None,
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


# --- 420: saves and save states -------------------------------------------------------------------------
SLOT = Annotated[int, Path(ge=0, le=SLOTS)]


def _bytes(data: bytes, media_type: str = "application/octet-stream") -> Response:
    return Response(content=data, media_type=media_type, headers=PRIVATE)


@router.get("/sittings/{sitting_id}/saves", response_model=RetroProgressOut)
async def sitting_saves(principal: Player, module: Module, sitting_id: UUID) -> RetroProgressOut:
    _, progress = await module.saves.of_sitting(principal, sitting_id)
    return _progress(progress)


@router.get("/sittings/{sitting_id}/sram", include_in_schema=False)
async def sitting_sram(principal: Player, module: Module, sitting_id: UUID) -> Response:
    """The game's own save, loaded when the game starts."""
    return _bytes(await module.saves.read(principal, sitting_id, "sram", 0))


@router.put("/sittings/{sitting_id}/sram", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
async def keep_sram(principal: Player, module: Module, sitting_id: UUID, request: Request) -> None:
    """The game's own save, as the emulator just wrote it (raw bytes)."""
    await module.saves.write(principal, sitting_id, "sram", 0, await request.body())


@router.get("/sittings/{sitting_id}/states/{slot}", include_in_schema=False)
async def sitting_state(principal: Player, module: Module, sitting_id: UUID, slot: SLOT) -> Response:
    return _bytes(await module.saves.read(principal, sitting_id, "state", slot))


@router.put("/sittings/{sitting_id}/states/{slot}", response_model=RetroStateOut, include_in_schema=False)
async def keep_state(
    principal: Player, module: Module, sitting_id: UUID, slot: SLOT, request: Request
) -> RetroStateOut:
    """A save state in a slot (raw bytes), replacing the slot's."""
    return _state(await module.saves.write(principal, sitting_id, "state", slot, await request.body()))


@router.delete("/sittings/{sitting_id}/states/{slot}", status_code=status.HTTP_204_NO_CONTENT)
async def drop_state(principal: Player, module: Module, sitting_id: UUID, slot: SLOT) -> None:
    await module.saves.remove(principal, sitting_id, slot)


@router.get("/sittings/{sitting_id}/states/{slot}/picture", include_in_schema=False)
async def state_picture(principal: Player, module: Module, sitting_id: UUID, slot: SLOT) -> Response:
    data, kind = await module.saves.picture(principal, sitting_id, slot)
    return _bytes(data, kind)


@router.get("/games/{object_id}/states/{slot}/picture", include_in_schema=False)
async def game_state_picture(principal: Player, module: Module, object_id: UUID, slot: SLOT) -> Response:
    """A save state's picture, for choosing where to resume from the game's page."""
    data, kind = await module.saves.picture_of_game(principal, object_id, slot)
    return _bytes(data, kind)


@router.put(
    "/sittings/{sitting_id}/states/{slot}/picture",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
async def keep_state_picture(
    principal: Player, module: Module, sitting_id: UUID, slot: SLOT, request: Request
) -> None:
    """The screen when the state was saved (PNG, JPEG or WebP)."""
    await module.saves.write_picture(principal, sitting_id, slot, await request.body())


# --- 421: the member's emulator settings ----------------------------------------------------------------
CORE = Annotated[str, Path(pattern=r"^[a-z0-9_]{1,64}$")]


class RetroPreferencesIn(BaseModel):
    data: dict[str, Any]


class RetroPreferencesOut(BaseModel):
    data: dict[str, Any] | None = None


@router.get("/preferences/{core}", response_model=RetroPreferencesOut)
async def retro_preferences(principal: Player, module: Module, core: CORE) -> RetroPreferencesOut:
    """The member's controls and options for a core (they follow the member from device to device)."""
    return RetroPreferencesOut(data=await module.saves.preferences(principal, core))


@router.put("/preferences/{core}", status_code=status.HTTP_204_NO_CONTENT)
async def keep_retro_preferences(
    principal: Player, module: Module, core: CORE, body: RetroPreferencesIn
) -> None:
    await module.saves.keep_preferences(principal, core, body.data)


# --- 426: each member's own account in the libraries ------------------------------------------------------
class RetroAccountOut(BaseModel):
    service_id: UUID
    service_name: str | None = None
    state: Literal["none", "pending", "linked", "expired"]
    username: str | None = None
    expires_at: datetime | None = None
    user_code: str | None = None  # pending: the code the member approves in the library
    approve_url: str | None = None
    pending_until: datetime | None = None
    interval: int = 5


def _account(state: AccountState) -> RetroAccountOut:
    return RetroAccountOut(
        service_id=state.service_id,
        service_name=state.service_name,
        state=state.state,
        username=state.username,
        expires_at=state.expires_at,
        user_code=state.user_code,
        approve_url=state.approve_url,
        pending_until=state.pending_until,
        interval=state.interval,
    )


@router.get("/accounts", response_model=list[RetroAccountOut])
async def retro_accounts(principal: Player, module: Module) -> list[RetroAccountOut]:
    """Whether the member's sessions and saves go to their own account in each library."""
    return [_account(state) for state in await module.accounts.states(principal)]


@router.post("/accounts/{service_id}", response_model=RetroAccountOut)
async def link_retro_account(principal: Player, module: Module, service_id: UUID) -> RetroAccountOut:
    """Ask the library for the member's authorisation: the code they approve there."""
    return _account(await module.accounts.begin(principal, service_id))


@router.post("/accounts/{service_id}/check", response_model=RetroAccountOut)
async def check_retro_account(principal: Player, module: Module, service_id: UUID) -> RetroAccountOut:
    return _account(await module.accounts.check(principal, service_id))


@router.delete("/accounts/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_retro_account(principal: Player, module: Module, service_id: UUID) -> None:
    await module.accounts.unlink(principal, service_id)
