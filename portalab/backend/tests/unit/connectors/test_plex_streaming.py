"""027 (#2) — Plex's ``media.streaming``: a shared member plays with the access token plex.tv issued them
(read with the owner's token), the title's versions, tracks, markers and chapters are mapped, the
member's audio/subtitle choice is stored on their account, the transcoder's decision is read, only the
stream's own playlist and segments are relayed, and the ASS subtitle feed becomes cues."""

import json
from collections.abc import AsyncIterator
from uuid import UUID

import httpx
import pytest

from portalab.capabilities.connector_http import ConnectorHttpClient
from portalab.capabilities.connector_sdk import ServiceHandle
from portalab.capabilities.media import StreamOptions
from portalab.capabilities.results import ProviderAuthError, ProviderNotFound
from portalab.connectors.plex import PlexConnector
from portalab.connectors.plex.streaming import _TOKENS, _cues

FILM = {
    "ratingKey": "100",
    "type": "movie",
    "title": "Alien",
    "year": 1979,
    "duration": 7_000_000,
    "viewOffset": 1_234_000,
    "thumb": "/t",
    "Marker": [{"type": "credits", "startTimeOffset": 6_800_000, "endTimeOffset": 7_000_000}],
    "Chapter": [
        {
            "tag": "Nostromo",
            "startTimeOffset": 0,
            "endTimeOffset": 600_000,
            "thumb": "/library/media/77/chapterImages/1",
        },
        {"startTimeOffset": 600_000, "endTimeOffset": 7_000_000},
    ],
    "Media": [
        {
            "videoResolution": "1080",
            "videoCodec": "h264",
            "container": "mkv",
            "bitrate": 8000,
            "width": 1920,
            "height": 800,
            "Part": [
                {
                    "id": 5,
                    "size": 10,
                    "indexes": "sd",
                    "Stream": [
                        {"id": 1, "streamType": 1, "codec": "h264", "displayTitle": "1080p"},
                        {
                            "id": 2,
                            "streamType": 2,
                            "codec": "eac3",
                            "extendedDisplayTitle": "VO",
                            "selected": True,
                        },
                        {"id": 3, "streamType": 3, "codec": "srt", "extendedDisplayTitle": "Français"},
                        {"id": 4, "streamType": 3, "codec": "pgs", "extendedDisplayTitle": "PGS"},
                    ],
                }
            ],
        }
    ],
}
ASS = (
    "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    "Dialogue: 0,0:00:01.50,0:00:03.00,Default,,0,0,0,,{\\i1}In space,{\\i0}\\Nno one hears\r\n"
    "Dialogue: 0,1:02:03.25,1:02:04.00,Default,,0,0,0,,you scream\n"
)


class _Server:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.url.host == "plex.tv":
            assert request.headers["X-Plex-Token"] == "owner"
            xml = '<MediaContainer><SharedServer userID="42" accessToken="tok42"/></MediaContainer>'
            return httpx.Response(200, text=xml)
        if path == "/identity":
            return httpx.Response(200, json={"MediaContainer": {"machineIdentifier": "M1"}})
        if path == "/library/metadata/100":
            return httpx.Response(200, json={"MediaContainer": {"Metadata": [FILM]}})
        if path == "/library/metadata/404":
            return httpx.Response(404)
        if path == "/library/parts/5":
            return httpx.Response(200)
        if path == "/photo/:/transcode" or path.startswith("/library/parts/5/indexes/sd/"):
            return httpx.Response(200, content=b"\xff\xd8jpeg")
        if path.endswith("/decision"):
            media = {
                "width": 1920,
                "height": 800,
                "bitrate": 5000,
                "videoCodec": "h264",
                "audioCodec": "aac",
                "Part": [
                    {
                        "Stream": [
                            {"streamType": 1, "decision": "copy"},
                            {"streamType": 2, "decision": "transcode"},
                        ]
                    }
                ],
            }
            return httpx.Response(200, json={"MediaContainer": {"Metadata": [{"Media": [media]}]}})
        if path.endswith("/start.m3u8"):
            session = request.url.params["session"]
            return httpx.Response(
                200, text=f"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nsession/{session}/base/index.m3u8\n"
            )
        if "/session/" in path:
            return httpx.Response(
                200, content=b"#EXTM3U\n", headers={"content-type": "application/vnd.apple.mpegurl"}
            )
        if path.endswith("/subtitles"):
            return httpx.Response(200, text=ASS)
        return httpx.Response(200)


@pytest.fixture
def server() -> _Server:
    _TOKENS.clear()
    return _Server()


def _streaming(server: _Server):  # type: ignore[no-untyped-def]
    http = ConnectorHttpClient("http://plex.lan:32400", transport=httpx.MockTransport(server), retries=0)
    handle = ServiceHandle(
        service_id=UUID(int=5), name="Plex", config={}, secrets={"token": "owner"}, http=http
    )
    return PlexConnector().provider("media.streaming", handle)


async def test_a_shared_member_plays_as_themself(server: _Server) -> None:
    channel = _streaming(server).channel("42")
    item = await channel.playable("100")
    assert (item.title, item.resume_s, item.duration_s) == ("Alien", 1234.0, 7000.0)
    version = item.versions[0]
    assert version.label == "1080p · H.264 · mkv"
    assert [(t.id, t.text) for t in version.subtitles] == [("3", True), ("4", False)]
    assert version.audio[0].selected and item.markers[0].kind == "credits"
    assert item.chapters[0].label == "Nostromo" and item.chapters[0].image == "chapter:77:1"
    assert item.chapters[1].label is None and item.chapters[1].image is None
    assert version.previews == "preview:5"
    assert await channel.image("chapter:77:1") == b"\xff\xd8jpeg"
    scaled = [r for r in server.requests if r.url.path == "/photo/:/transcode"][-1]
    assert (
        scaled.url.params["url"] == "/library/media/77/chapterImages/1"
        and scaled.url.params["width"] == "320"
    )
    assert await channel.image("preview:5", 61.5) == b"\xff\xd8jpeg"
    assert server.requests[-1].url.path == "/library/parts/5/indexes/sd/61500"
    for bad in ("chapter:77", "preview:5:1", "file:/etc/passwd", "chapter:../1:1"):
        with pytest.raises(ProviderNotFound):
            await channel.image(bad)
    plex_calls = [r for r in server.requests if r.url.host == "plex.lan"]
    assert {r.headers["X-Plex-Token"] for r in plex_calls if r.url.path != "/identity"} == {"tok42"}

    started = await channel.start("100", StreamOptions(quality="4m", audio="2", subtitle="3"), "sess1")
    assert (started.video, started.audio, started.subtitles) == ("copy", "transcode", "text")
    assert started.playlist == "session/sess1/base/index.m3u8"
    selection = next(r for r in server.requests if r.url.path == "/library/parts/5")
    assert selection.method == "PUT" and selection.url.params["subtitleStreamID"] == "3"
    decision = next(r for r in server.requests if r.url.path.endswith("/decision"))
    assert decision.url.params["maxVideoBitrate"] == "4000" and decision.url.params["subtitles"] == "auto"

    async with channel.open("sess1", "session/sess1/base/index.m3u8") as body:
        assert body.content_type == "application/vnd.apple.mpegurl"
        assert b"".join([chunk async for chunk in body.chunks]) == b"#EXTM3U\n"
    with pytest.raises(ProviderNotFound):
        async with channel.open("sess1", "session/other/base/00000.ts"):
            pass
    with pytest.raises(ProviderNotFound):
        async with channel.open("sess1", "session/sess1/../../library/sections"):
            pass

    await channel.report("100", "sess1", "paused", 12.5, 7000.0)
    timeline = next(r for r in server.requests if r.url.path == "/:/timeline")
    assert timeline.url.params["time"] == "12500" and timeline.url.params["state"] == "paused"
    assert any(r.url.path.endswith("/ping") for r in server.requests)  # a paused stream is kept alive


async def test_an_image_subtitle_is_burnt_and_unknown_accounts_refused(server: _Server) -> None:
    owner = _streaming(server).channel(None)
    started = await owner.start("100", StreamOptions(subtitle="4"), "sess2")
    assert started.subtitles == "burn"
    decision = [r for r in server.requests if r.url.path.endswith("/decision")][-1]
    assert decision.url.params["subtitles"] == "burn" and decision.url.params["maxVideoBitrate"] == "200000"
    assert all(r.url.host != "plex.tv" for r in server.requests)  # the owner needs no lookup
    with pytest.raises(ProviderAuthError):
        await _streaming(server).channel("99").playable("100")
    with pytest.raises(ProviderNotFound):
        await owner.playable("404")


async def test_the_subtitle_feed_becomes_cues() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        data = ASS.encode()
        for i in range(0, len(data), 7):  # split anywhere, even inside a character
            yield data[i : i + 7]
        yield b"WEBVTT\n\n00:01:00.000 --> 00:01:02.500 align:center\nHello\nthere\n\n"

    cues = [cue async for cue in _cues(chunks())]
    assert [(c.start_s, c.end_s, c.text) for c in cues] == [
        (1.5, 3.0, "In space,\nno one hears"),
        (3723.25, 3724.0, "you scream"),
        (60.0, 62.5, "Hello\nthere"),
    ]


def test_capability_is_declared() -> None:
    names = [b.spec.name for b in PlexConnector.provides]
    assert "media.streaming" in names
    assert json.dumps(names)  # the bindings stay plain names
