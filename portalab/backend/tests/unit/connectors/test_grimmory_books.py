"""#20, #21 — Grimmory's ``media.audio`` and ``media.reading``: an audiobook's chapters and files, its audio
relayed with the member's byte range, a book's formats and a comic's pages; the position is read from and
written back to Grimmory only for the account configured on the service (whose progress Grimmory keeps)."""

import json
from uuid import UUID

import httpx
import pytest

from portalab.capabilities.connector_http import ConnectorHttpClient
from portalab.capabilities.connector_sdk import ServiceHandle
from portalab.capabilities.media import AUDIO, READING, AudioPosition, ReadableBook, ReadingPosition
from portalab.capabilities.results import ProviderNotFound
from portalab.connectors.grimmory import GrimmoryConnector
from portalab.connectors.grimmory.books import audio_item, parse_ref

AUDIOBOOK = {
    "id": 7,
    "metadata": {"title": "La reine", "authors": [{"name": "Ann"}, {"name": "Bob"}]},
    "primaryFile": {"id": 70, "bookType": "AUDIOBOOK"},
    "audiobookProgress": {"positionMs": 125000, "trackIndex": 1, "percentage": 12.5},
    "lastReadTime": "2026-02-01T10:00:00Z",
}
INFO = {
    "bookId": 7,
    "bookFileId": 70,
    "title": "La reine",
    "narrator": "Nina",
    "durationMs": 1_000_000,
    "codec": "aac",
    "bitrate": 64000,
    "folderBased": True,
    "chapters": [{"index": 0, "title": "Un", "startTimeMs": 0, "endTimeMs": 400_000}],
    "tracks": [
        {"index": 0, "fileName": "01.mp3", "durationMs": 400_000, "cumulativeStartMs": 0},
        {"index": 1, "title": "Deux", "durationMs": 600_000, "cumulativeStartMs": 400_000},
    ],
}
NOVEL = {
    "id": 9,
    "metadata": {"title": "Roman"},
    "primaryFile": {"id": 90, "bookType": "EPUB", "fileSizeKb": 2},
    "alternativeFormats": [{"id": 91, "bookType": "CBX"}, {"id": 92, "bookType": "AUDIOBOOK"}],
    "epubProgress": {"cfi": "epubcfi(/6/2)", "percentage": 40},
    "cbxProgress": {"page": 3, "percentage": 10},
}


class _Server:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/api/v1/auth/login":
            return httpx.Response(200, json={"accessToken": "tok", "expires": 3600})
        if path == "/api/v1/users":
            return httpx.Response(200, json=[{"id": 1, "username": "me"}, {"id": 2, "username": "you"}])
        if path == "/api/v1/books/7":
            return httpx.Response(200, json=AUDIOBOOK)
        if path == "/api/v1/books/9":
            return httpx.Response(200, json=NOVEL)
        if path == "/api/v1/audiobooks/7/info":
            return httpx.Response(200, json=INFO)
        if path == "/api/v1/audiobooks/7/track/1/stream":
            assert request.headers["authorization"] == "Bearer tok"
            assert request.headers.get("accept-encoding") == "identity"
            return httpx.Response(
                206,
                content=b"abc",
                headers={"content-type": "audio/mpeg", "content-range": "bytes 0-2/10"},
            )
        if path == "/api/v1/books/9/content":
            assert request.url.params["bookType"] == "EPUB"
            return httpx.Response(200, content=b"PK", headers={"content-type": "application/epub+zip"})
        if path == "/api/v1/cbx/9/pages":
            return httpx.Response(200, json=[1, 2, 3])
        if path == "/api/v1/media/book/9/cbx/pages/2":
            return httpx.Response(200, content=b"\xff\xd8", headers={"content-type": "image/jpeg"})
        if path == "/api/v1/books/progress":
            return httpx.Response(200)
        return httpx.Response(404)

    def progress(self) -> list[dict[str, object]]:
        return [json.loads(r.content) for r in self.requests if r.url.path == "/api/v1/books/progress"]


@pytest.fixture
def server() -> _Server:
    return _Server()


def _provider(server: _Server, capability: str):  # type: ignore[no-untyped-def]
    http = ConnectorHttpClient("http://books.lan", transport=httpx.MockTransport(server), retries=0)
    handle = ServiceHandle(
        service_id=UUID(int=8),
        name="Grimmory",
        config={"username": "me"},
        secrets={"password": "x"},
        http=http,
    )
    return GrimmoryConnector().provider(capability, handle)


async def test_an_audiobook_as_the_configured_account(server: _Server) -> None:
    channel = _provider(server, AUDIO).channel("1")  # the member linked to « me »
    item = await channel.item("7")
    assert (item.title, item.author, item.narrator, item.duration_s) == (
        "La reine",
        "Ann, Bob",
        "Nina",
        1000.0,
    )
    assert [(t.title, t.start_s) for t in item.tracks] == [("01.mp3", 0.0), ("Deux", 400.0)]
    assert item.chapters[0].end_s == 400.0 and item.bitrate_kbps == 64 and item.file_ref == "70"
    chapterless = audio_item(AUDIOBOOK, {**INFO, "chapters": []}, own=False)
    assert [(c.title, c.start_s, c.end_s) for c in chapterless.chapters] == [
        ("01.mp3", 0.0, 400.0),
        ("Deux", 400.0, 1000.0),
    ]
    assert item.position is not None and (item.position.position_s, item.position.track) == (125.0, 1)
    assert item.position.percent == 0.125

    async with channel.open("7", 1, "bytes=0-2") as body:
        assert (body.status, body.content_range) == (206, "bytes 0-2/10")
        assert b"".join([chunk async for chunk in body.chunks]) == b"abc"
    assert server.requests[-1].headers["range"] == "bytes=0-2"

    await channel.report(item, AudioPosition(position_s=500.0, track=1, percent=0.5))
    assert server.progress()[-1] == {
        "bookId": 7,
        "fileProgress": {
            "bookFileId": 70,
            "positionData": "500000",
            "positionHref": "1",
            "progressPercent": 50.0,
        },
    }


async def test_another_account_reads_nothing_and_writes_nothing(server: _Server) -> None:
    channel = _provider(server, AUDIO).channel("2")
    item = await channel.item("7")
    assert item.position is None
    await channel.report(item, AudioPosition(position_s=5.0))
    unlinked = _provider(server, AUDIO).channel(None)
    await unlinked.report(await unlinked.item("7"), AudioPosition(position_s=5.0))
    assert server.progress() == []


async def test_a_book_its_formats_and_pages(server: _Server) -> None:
    channel = _provider(server, READING).channel("1")
    book = await channel.book("9")
    assert [(f.file_ref, f.format, f.size) for f in book.formats] == [
        ("90.epub", "epub", 2048),
        ("91.cbx", "cbx", None),
    ]
    assert {p.format: (p.position, p.percent) for p in book.positions} == {
        "epub": ("epubcfi(/6/2)", 0.4),
        "cbx": ("3", 0.1),
    }
    async with channel.open("9", "90.epub") as body:
        assert body.content_type == "application/epub+zip"
    assert await channel.pages("9", "91.cbx") == [1, 2, 3]
    async with channel.page("9", "91.cbx", 2) as body:
        assert body.content_type == "image/jpeg"

    await channel.report(
        ReadableBook(external_id="9", title=""),
        ReadingPosition(format="epub", position="epubcfi(/6/8)", percent=0.75, file_ref="90.epub"),
    )
    assert server.progress()[-1]["fileProgress"] == {
        "bookFileId": 90,
        "positionData": "epubcfi(/6/8)",
        "positionHref": None,
        "progressPercent": 75.0,
    }
    other = await _provider(server, READING).channel("2").book("9")
    assert other.positions == ()


def test_file_references() -> None:
    assert parse_ref("12.pdf") == ("12", "pdf")
    for bad in ("12", "12.exe", ".epub", "x.mp3"):
        with pytest.raises(ProviderNotFound):
            parse_ref(bad)
