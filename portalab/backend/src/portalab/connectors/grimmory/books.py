"""Grimmory in the portal's own listening and reading (#20, #21).

* ``media.audio``: an audiobook's chapters and files (``/api/v1/audiobooks/{id}/info``), its audio relayed
  with byte ranges (``…/stream``, ``trackIndex`` for a book made of several files).
* ``media.reading``: a book's formats (its primary file and the alternative ones), the whole file
  (``/api/v1/books/{id}/content?bookType=``) or a comic's pages (``/api/v1/cbx/{id}/pages``,
  ``/api/v1/media/book/{id}/cbx/pages/{n}``).

Grimmory reveals and keeps the progress of the signed-in account only — the one configured on the
service. So a member's position is read from and written back to Grimmory only when the member's linked
Grimmory account *is* that one; everyone else's position stays in the portal (``POST /api/v1/books/progress``
with a ``fileProgress``: a percent from 0 to 100, the position as text).
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from portalab.capabilities.media import (
    AudioChapter,
    AudioItem,
    AudioPosition,
    AudioTrack,
    BookFormat,
    ReadableBook,
    ReadingPosition,
    StreamBody,
)
from portalab.capabilities.results import InvalidPayload, ProviderAuthError, ProviderNotFound
from portalab.connectors.http_base import parse_time, safe_id

if TYPE_CHECKING:
    from portalab.capabilities.connector_sdk import ServiceHandle
    from portalab.connectors.grimmory import GrimmoryConnector

# Grimmory's file types, as the reader names them
FORMATS = {"EPUB": "epub", "PDF": "pdf", "CBX": "cbx", "MOBI": "mobi", "AZW3": "azw3", "FB2": "fb2"}
TYPES = {value: key for key, value in FORMATS.items()}
AUDIO_TYPES = {
    "mp3": "audio/mpeg",
    "m4b": "audio/mp4",
    "m4a": "audio/mp4",
    "opus": "audio/ogg",
}


def _ms(value: Any) -> float | None:
    try:
        return float(value) / 1000 if value is not None else None
    except (TypeError, ValueError):
        return None


def _authors(book: Mapping[str, Any]) -> str | None:
    meta = book.get("metadata") if isinstance(book.get("metadata"), Mapping) else {}
    raw = [
        (a.get("name") if isinstance(a, Mapping) else a)
        for a in (meta.get("authors") if isinstance(meta, Mapping) else None) or []
    ]
    names = [n.strip() for n in raw if isinstance(n, str) and n.strip()]
    return ", ".join(names[:3]) or None


def _title(book: Mapping[str, Any]) -> str:
    meta = book.get("metadata") if isinstance(book.get("metadata"), Mapping) else {}
    return str((meta.get("title") if isinstance(meta, Mapping) else None) or book.get("title") or "?")[:500]


def file_ref(file: Mapping[str, Any]) -> str | None:
    """``<file id>.<format>``: the reader asks for a file by it, the service is asked by id and type."""
    kind = FORMATS.get(str(file.get("bookType") or "").upper())
    if file.get("id") is None or kind is None:
        return None
    return f"{safe_id(file['id'])}.{kind}"


def parse_ref(ref: str) -> tuple[str, str]:
    file_id, _, kind = ref.partition(".")
    if not file_id or kind not in TYPES:
        raise ProviderNotFound("no such file")
    return safe_id(file_id), kind


def formats(book: Mapping[str, Any]) -> tuple[BookFormat, ...]:
    files = [book.get("primaryFile"), *(book.get("alternativeFormats") or [])]
    out: list[BookFormat] = []
    for file in files:
        if not isinstance(file, Mapping):
            continue
        ref = file_ref(file)
        if ref is None:
            continue
        size = file.get("fileSizeKb")
        out.append(
            BookFormat(
                file_ref=ref,
                format=ref.split(".", 1)[1],
                size=int(size) * 1024 if isinstance(size, int | float) else None,
            )
        )
    return tuple(out)


def positions(book: Mapping[str, Any]) -> tuple[ReadingPosition, ...]:
    """The account's position in each format, as Grimmory keeps it on the book (percent 0..100)."""
    at = parse_time(book.get("lastReadTime"))
    out: list[ReadingPosition] = []
    epub = book.get("epubProgress")
    if isinstance(epub, Mapping) and epub.get("cfi"):
        out.append(ReadingPosition("epub", str(epub["cfi"]), _share(epub.get("percentage")), at=at))
    for name in ("pdf", "cbx"):
        progress = book.get(f"{name}Progress")
        if isinstance(progress, Mapping) and progress.get("page") is not None:
            out.append(
                ReadingPosition(name, str(progress["page"]), _share(progress.get("percentage")), at=at)
            )
    return tuple(out)


def _share(percentage: Any) -> float:
    try:
        return min(1.0, max(0.0, float(percentage) / 100))
    except (TypeError, ValueError):
        return 0.0


def audio_item(book: Mapping[str, Any], info: Mapping[str, Any], *, own: bool) -> AudioItem:
    chapters = tuple(
        AudioChapter(
            index=int(c.get("index") or i),
            title=str(c.get("title") or f"{i + 1}")[:300],
            start_s=_ms(c.get("startTimeMs")) or 0.0,
            end_s=_ms(c.get("endTimeMs")) or 0.0,
        )
        for i, c in enumerate(info.get("chapters") or [])
        if isinstance(c, Mapping)
    )
    tracks: tuple[AudioTrack, ...] = ()
    if info.get("folderBased"):
        tracks = tuple(
            AudioTrack(
                index=t["index"] if isinstance(t.get("index"), int) else i,
                title=str(t.get("title") or t.get("fileName") or f"{i + 1}")[:300],
                start_s=_ms(t.get("cumulativeStartMs")) or 0.0,
                duration_s=_ms(t.get("durationMs")) or 0.0,
                size=int(t["fileSizeBytes"]) if isinstance(t.get("fileSizeBytes"), int) else None,
            )
            for i, t in enumerate(info.get("tracks") or [])
            if isinstance(t, Mapping)
        )
    if not chapters and len(tracks) > 1:  # a file per chapter, none declared: the files are the chapters
        chapters = tuple(AudioChapter(t.index, t.title, t.start_s, t.start_s + t.duration_s) for t in tracks)
    duration = _ms(info.get("durationMs"))
    position = None
    progress = book.get("audiobookProgress")
    if own and isinstance(progress, Mapping) and progress.get("positionMs") is not None:
        position = AudioPosition(
            position_s=_ms(progress.get("positionMs")) or 0.0,
            track=progress.get("trackIndex") if isinstance(progress.get("trackIndex"), int) else None,
            percent=_share(progress.get("percentage")),
            at=parse_time(book.get("lastReadTime")),
        )
    file_id = info.get("bookFileId")
    return AudioItem(
        external_id=safe_id(book.get("id") or info.get("bookId")),
        kind="audiobook",
        title=str(info.get("title") or _title(book))[:500],
        author=(str(info["author"])[:300] if info.get("author") else _authors(book)),
        narrator=(str(info["narrator"])[:300] if info.get("narrator") else None),
        duration_s=duration,
        chapters=chapters,
        tracks=tracks,
        codec=(str(info["codec"])[:40] if info.get("codec") else None),
        bitrate_kbps=(int(info["bitrate"]) // 1000 if isinstance(info.get("bitrate"), int) else None),
        position=position,
        file_ref=safe_id(file_id) if file_id is not None else None,
    )


class _Account:
    """Whether this channel's account is the service's configured one (whose progress Grimmory keeps)."""

    def __init__(self, connector: "GrimmoryConnector", service: "ServiceHandle", account: str | None) -> None:
        self.connector, self.service, self.account = connector, service, account

    async def own(self) -> bool:
        if self.account is None:
            return False
        return self.account == await self.connector.self_id(self.service)

    @asynccontextmanager
    async def _relay(
        self, path: str, params: Mapping[str, Any], headers: Mapping[str, str], fallback: str
    ) -> AsyncIterator[StreamBody]:
        await self.connector._ensure(self.service)
        sent = {**self.connector.auth_headers(self.service), "Accept-Encoding": "identity", **headers}
        async with self.connector._http(self.service).stream(
            "GET",
            path,
            headers=sent,
            params={k: v for k, v in params.items() if v is not None},
            read_timeout=60,
        ) as response:
            if response.status_code in (401, 403):
                raise ProviderAuthError("the service refused this account")
            if response.status_code in (404, 410):
                raise ProviderNotFound("no such file")
            if response.status_code == 416:
                raise InvalidPayload("range not satisfiable")
            if response.status_code >= 400:
                raise ConnectionError(f"the service answered HTTP {response.status_code}")
            encoded = response.headers.get("content-encoding", "identity") != "identity"
            length = None if encoded else response.headers.get("content-length")
            yield StreamBody(
                status=response.status_code,
                content_type=response.headers.get("content-type") or fallback,
                length=int(length) if length and length.isdigit() else None,
                chunks=response.chunks,
                content_range=response.headers.get("content-range"),
            )

    async def _book(self, external_id: str) -> Mapping[str, Any]:
        book = await self.connector.get_json(self.service, f"/api/v1/books/{safe_id(external_id)}")
        if not isinstance(book, Mapping):
            raise InvalidPayload("not a Grimmory book")
        return book

    async def _progress(
        self, book_id: str, file_id: str, position: str, href: str | None, share: float
    ) -> None:
        await self.connector.request(
            self.service,
            "POST",
            "/api/v1/books/progress",
            json_body={
                "bookId": int(book_id) if book_id.isdigit() else book_id,
                "fileProgress": {
                    "bookFileId": int(file_id) if file_id.isdigit() else file_id,
                    "positionData": position,
                    "positionHref": href,
                    "progressPercent": round(min(100.0, max(0.0, share * 100)), 2),
                },
            },
        )


class AudioChannel(_Account):
    async def item(self, external_id: str) -> AudioItem:
        book_id = safe_id(external_id)
        book = await self._book(book_id)
        info = await self.connector.get_json(self.service, f"/api/v1/audiobooks/{book_id}/info")
        if not isinstance(info, Mapping):
            raise InvalidPayload("not a Grimmory audiobook")
        return audio_item(book, info, own=await self.own())

    def open(
        self, external_id: str, track: int | None, byte_range: str | None
    ) -> Any:  # an async context manager of StreamBody
        book_id = safe_id(external_id)
        path = (
            f"/api/v1/audiobooks/{book_id}/track/{int(track)}/stream"
            if track is not None
            else f"/api/v1/audiobooks/{book_id}/stream"
        )
        return self._relay(path, {}, {"Range": byte_range} if byte_range else {}, "audio/mpeg")

    async def report(self, item: AudioItem, position: AudioPosition) -> None:
        if item.file_ref is None or not await self.own():
            return
        share = position.percent
        if share is None and item.duration_s:
            share = position.position_s / item.duration_s
        await self._progress(
            item.external_id,
            item.file_ref,
            str(int(position.position_s * 1000)),
            str(position.track) if position.track is not None else None,
            share or 0.0,
        )


class ReadingChannel(_Account):
    async def book(self, external_id: str) -> ReadableBook:
        book = await self._book(external_id)
        return ReadableBook(
            external_id=safe_id(book.get("id") or external_id),
            title=_title(book),
            author=_authors(book),
            formats=formats(book),
            positions=positions(book) if await self.own() else (),
        )

    def open(self, external_id: str, file_ref: str) -> Any:
        _, kind = parse_ref(file_ref)
        fallback = "application/epub+zip" if kind == "epub" else "application/pdf"
        return self._relay(
            f"/api/v1/books/{safe_id(external_id)}/content", {"bookType": TYPES[kind]}, {}, fallback
        )

    async def pages(self, external_id: str, file_ref: str) -> list[int]:
        _, kind = parse_ref(file_ref)
        found = await self.connector.get_json(
            self.service, f"/api/v1/cbx/{safe_id(external_id)}/pages", bookType=TYPES[kind]
        )
        return [int(n) for n in found or [] if isinstance(n, int)]

    def page(self, external_id: str, file_ref: str, number: int) -> Any:
        _, kind = parse_ref(file_ref)
        return self._relay(
            f"/api/v1/media/book/{safe_id(external_id)}/cbx/pages/{int(number)}",
            {"bookType": TYPES[kind]},
            {},
            "image/jpeg",
        )

    async def report(self, book: ReadableBook, position: ReadingPosition) -> None:
        if position.file_ref is None or not await self.own():
            return
        file_id, _ = parse_ref(position.file_ref)
        await self._progress(book.external_id, file_id, position.position, None, position.percent)


class Listening:
    def __init__(self, connector: "GrimmoryConnector", service: "ServiceHandle") -> None:
        self.connector, self.service = connector, service

    def channel(self, external_user_id: str | None) -> AudioChannel:
        return AudioChannel(self.connector, self.service, external_user_id)


class Reading:
    def __init__(self, connector: "GrimmoryConnector", service: "ServiceHandle") -> None:
        self.connector, self.service = connector, service

    def channel(self, external_user_id: str | None) -> ReadingChannel:
        return ReadingChannel(self.connector, self.service, external_user_id)
