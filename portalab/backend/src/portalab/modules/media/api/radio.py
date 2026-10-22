"""HTTP API of the homelab's radio (issue 168): what plays, the live stream and the covers (relayed — the
portal is served over HTTPS, the station often not), and asking its DJ for a song."""

import time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Path
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.media.api.router import Module, _me
from portalab.modules.media.permissions import MEDIA_PLAY
from portalab.modules.media.radio import LISTEN_MINUTES

router = APIRouter(prefix="/api/v1", tags=["media"])
Listener = Annotated[Principal, require(MEDIA_PLAY)]
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


class RadioTrackOut(BaseModel):
    title: str
    artist: str | None = None
    album: str | None = None
    year: int | None = None
    genre: str | None = None
    cover_ref: str | None = None
    started_at: str | None = None
    duration: float | None = None
    requested_by: str | None = None


class RadioAllowanceOut(BaseModel):
    free_per_day: int
    free_left: int
    credits: int


class RadioOut(BaseModel):
    available: bool
    station: str | None = None
    on_air: bool = False
    host: str | None = None
    tagline: str | None = None
    listeners: int | None = None
    mood: str | None = None
    current: RadioTrackOut | None = None
    upcoming: list[RadioTrackOut] = Field(default_factory=list)
    recent: list[RadioTrackOut] = Field(default_factory=list)
    # issue 184: what the member may still ask today — free requests left, credits held
    allowance: RadioAllowanceOut | None = None


class RadioAskIn(BaseModel):
    text: str = Field(min_length=1, max_length=280)


class RadioRequestOut(BaseModel):
    id: str | None
    status: str
    detail: str | None = None
    track: RadioTrackOut | None = None
    allowance: RadioAllowanceOut | None = None


@router.get("/media/radio", response_model=RadioOut)
async def radio(principal: Listener, module: Module) -> dict[str, Any]:
    state = await module.radio.state()
    if state.get("available"):
        state["allowance"] = await module.radio.allowance(_me(principal))
    return state


@router.post("/media/radio/requests", response_model=RadioRequestOut)
async def ask_radio(principal: Listener, body: RadioAskIn, module: Module) -> dict[str, Any]:
    return await module.radio.ask(_me(principal), body.text)


@router.get("/media/radio/requests/{request_id}", response_model=RadioRequestOut)
async def radio_request(
    principal: Listener, module: Module, request_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")]
) -> dict[str, Any]:
    return await module.radio.request_status(request_id)


@router.get("/media/radio/stream", include_in_schema=False)
async def radio_stream(principal: Listener, module: Module) -> StreamingResponse:
    """The live stream, relayed as it plays (until the member stops listening). Issue 227: every
    ``LISTEN_MINUTES`` it was relayed counts as a slice of listening for this member (the server's count)."""
    stack = AsyncExitStack()
    body = await stack.enter_async_context(module.radio.listen())
    user = principal.acting_for or principal.user_id
    session = uuid4().hex

    async def relay() -> AsyncIterator[bytes]:
        started = time.monotonic()
        counted = 0
        try:
            async for chunk in body.chunks:
                yield chunk
                heard = int((time.monotonic() - started) // (LISTEN_MINUTES * 60))
                while user is not None and counted < heard:
                    counted += 1
                    await module.radio.listened(user, session, counted)
        finally:
            await stack.aclose()

    return StreamingResponse(relay(), media_type=body.content_type, headers=dict(NO_STORE))


@router.get("/media/radio/covers/{cover_ref}", response_class=Response)
async def radio_cover(
    principal: Listener, module: Module, cover_ref: Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,80}$")]
) -> Response:
    data = await module.radio.cover(cover_ref)
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )
