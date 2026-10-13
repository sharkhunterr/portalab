"""HTTP API of listening and reading in the portal (#20, #21).

``GET /media/{id}/listen`` describes an audiobook (chapters, files, where the member stopped) with a signed
ticket; the browser's audio element then reads ``/media/listen/{ticket}/audio`` (relayed from the library,
with byte ranges so it can seek) and reports where it is. ``GET /media/{id}/read`` describes a book (its
formats, where the member stopped in each); the reader fetches the file or a comic's pages under the
ticket and reports its position.
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Path, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from portalab.capabilities.media import AudioPosition, ReadingPosition, StreamBody
from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.media.api.router import Module, _me
from portalab.modules.media.permissions import MEDIA_PLAY

router = APIRouter(prefix="/api/v1", tags=["media"])
Reader = Annotated[Principal, require(MEDIA_PLAY)]
TICKET = r"^[A-Za-z0-9_-]{20,2000}\.[A-Za-z0-9_-]{10,40}$"
FILE = r"^[A-Za-z0-9_-]{1,60}\.(epub|pdf|cbx)$"
PRIVATE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


class AudioChapterOut(BaseModel):
    index: int
    title: str
    start_s: float
    end_s: float


class AudioTrackOut(BaseModel):
    index: int
    title: str
    start_s: float
    duration_s: float


class AudioPositionOut(BaseModel):
    position_s: float
    track: int | None
    percent: float | None


class AudioItemOut(BaseModel):
    external_id: str
    kind: str
    title: str
    author: str | None
    narrator: str | None
    duration_s: float | None
    chapters: list[AudioChapterOut]
    tracks: list[AudioTrackOut]
    codec: str | None
    bitrate_kbps: int | None


class ListenOut(BaseModel):
    ticket: str
    service_name: str | None
    synced: bool  # the library keeps the member's position too
    item: AudioItemOut
    resume: AudioPositionOut | None


class ListenPositionIn(BaseModel):
    state: str = Field(pattern=r"^(playing|paused|stopped|finished)$")
    position_s: float = Field(ge=0, le=10**7)
    duration_s: float | None = Field(default=None, ge=0, le=10**7)
    track: int | None = Field(default=None, ge=0, le=10_000)
    seq: int = Field(ge=0, le=10**6)


class BookFormatOut(BaseModel):
    file_ref: str
    format: str
    size: int | None


class ReadingPositionOut(BaseModel):
    format: str
    position: str
    percent: float
    file_ref: str | None


class BookOut(BaseModel):
    external_id: str
    title: str
    author: str | None
    formats: list[BookFormatOut]


class ReadOut(BaseModel):
    ticket: str
    service_name: str | None
    synced: bool
    book: BookOut
    resume: list[ReadingPositionOut]


class ReadPositionIn(BaseModel):
    state: str = Field(pattern=r"^(playing|paused|stopped|finished)$")
    format: str = Field(pattern=r"^(epub|pdf|cbx)$")
    file_ref: str | None = Field(default=None, pattern=FILE)
    position: str = Field(min_length=1, max_length=2000)
    percent: float = Field(ge=0, le=1)
    seconds: float = Field(default=0, ge=0, le=10**7)  # time spent reading in this session
    seq: int = Field(ge=0, le=10**6)


class PagesOut(BaseModel):
    pages: list[int]


def _resume(position: AudioPosition | None) -> AudioPositionOut | None:
    if position is None:
        return None
    return AudioPositionOut(position_s=position.position_s, track=position.track, percent=position.percent)


def _reading(position: ReadingPosition) -> ReadingPositionOut:
    return ReadingPositionOut(
        format=position.format,
        position=position.position,
        percent=position.percent,
        file_ref=position.file_ref,
    )


def _relay(body: StreamBody, stack: AsyncExitStack, headers: dict[str, str]) -> StreamingResponse:
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
    return StreamingResponse(relay(), status_code=body.status, media_type=body.content_type, headers=sent)


@router.get("/media/{object_id}/listen", response_model=ListenOut)
async def listen_info(principal: Reader, object_id: UUID, module: Module) -> ListenOut:
    found = await module.books.listen(_me(principal), object_id)
    item = found.item
    return ListenOut(
        ticket=found.ticket,
        service_name=found.service_name,
        synced=found.synced,
        item=AudioItemOut(
            external_id=item.external_id,
            kind=item.kind,
            title=item.title,
            author=item.author,
            narrator=item.narrator,
            duration_s=item.duration_s,
            chapters=[
                AudioChapterOut(index=c.index, title=c.title, start_s=c.start_s, end_s=c.end_s)
                for c in item.chapters
            ],
            tracks=[
                AudioTrackOut(index=t.index, title=t.title, start_s=t.start_s, duration_s=t.duration_s)
                for t in item.tracks
            ],
            codec=item.codec,
            bitrate_kbps=item.bitrate_kbps,
        ),
        resume=_resume(found.resume),
    )


@router.get("/media/listen/{ticket}/audio", include_in_schema=False)
async def listen_audio(
    principal: Reader,
    module: Module,
    ticket: Annotated[str, Path(pattern=TICKET)],
    track: Annotated[int | None, Query(ge=0, le=10_000)] = None,
    range_header: Annotated[str | None, Header(alias="Range", max_length=100)] = None,
) -> StreamingResponse:
    """The audio, relayed as the library sends it — a 206 for a range, so the member can seek."""
    stack = AsyncExitStack()
    body = await module.books.audio(_me(principal), ticket, track, range_header, stack)
    return _relay(body, stack, {**PRIVATE, "Accept-Ranges": "bytes"})


@router.post("/media/listen/{ticket}/position", status_code=status.HTTP_204_NO_CONTENT)
async def listen_position(
    principal: Reader, module: Module, ticket: Annotated[str, Path(pattern=TICKET)], body: ListenPositionIn
) -> None:
    await module.books.listened(
        _me(principal),
        ticket,
        state=body.state,
        position_s=body.position_s,
        duration_s=body.duration_s,
        track=body.track,
        seq=body.seq,
    )


@router.get("/media/{object_id}/read", response_model=ReadOut)
async def read_info(principal: Reader, object_id: UUID, module: Module) -> ReadOut:
    found = await module.books.read(_me(principal), object_id)
    book = found.book
    return ReadOut(
        ticket=found.ticket,
        service_name=found.service_name,
        synced=found.synced,
        book=BookOut(
            external_id=book.external_id,
            title=book.title,
            author=book.author,
            formats=[BookFormatOut(file_ref=f.file_ref, format=f.format, size=f.size) for f in book.formats],
        ),
        resume=[_reading(p) for p in found.resume.values()],
    )


@router.get("/media/read/{ticket}/file/{file_ref}", include_in_schema=False)
async def read_file(
    principal: Reader,
    module: Module,
    ticket: Annotated[str, Path(pattern=TICKET)],
    file_ref: Annotated[str, Path(pattern=FILE)],
) -> StreamingResponse:
    """The whole EPUB or PDF, for the reader to open — never shown by the browser as a page of the portal
    (``attachment``, and sandboxed if opened anyway)."""
    stack = AsyncExitStack()
    body = await module.books.file(_me(principal), ticket, file_ref, stack)
    return _relay(
        body,
        stack,
        {
            **PRIVATE,
            "Content-Disposition": "attachment",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )


@router.get("/media/read/{ticket}/pages/{file_ref}", response_model=PagesOut)
async def read_pages(
    principal: Reader,
    module: Module,
    ticket: Annotated[str, Path(pattern=TICKET)],
    file_ref: Annotated[str, Path(pattern=FILE)],
) -> PagesOut:
    return PagesOut(pages=await module.books.pages(_me(principal), ticket, file_ref))


@router.get("/media/read/{ticket}/page/{file_ref}/{number}", include_in_schema=False)
async def read_page(
    principal: Reader,
    module: Module,
    ticket: Annotated[str, Path(pattern=TICKET)],
    file_ref: Annotated[str, Path(pattern=FILE)],
    number: Annotated[int, Path(ge=0, le=100_000)],
) -> StreamingResponse:
    """One page of a comic book archive (an image)."""
    stack = AsyncExitStack()
    body = await module.books.page(_me(principal), ticket, file_ref, number, stack)
    return _relay(
        body, stack, {"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"}
    )


@router.post("/media/read/{ticket}/position", status_code=status.HTTP_204_NO_CONTENT)
async def read_position(
    principal: Reader, module: Module, ticket: Annotated[str, Path(pattern=TICKET)], body: ReadPositionIn
) -> None:
    await module.books.progressed(
        _me(principal),
        ticket,
        state=body.state,
        format=body.format,
        file_ref=body.file_ref,
        position=body.position,
        percent=body.percent,
        seconds=body.seconds,
        seq=body.seq,
    )
