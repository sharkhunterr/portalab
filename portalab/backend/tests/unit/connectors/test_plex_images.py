"""Issue 461 — Plex's posters through its photo transcoder (no redirect to the artwork's own host), and a
picture kept on another host is an answer about that item: never an outage counted against Plex."""

from uuid import UUID

import httpx
import pytest

from portalab.capabilities.connector_http import ConnectorHttpClient
from portalab.capabilities.connector_sdk import ServiceHandle
from portalab.capabilities.results import ProviderNotFound
from portalab.connectors.plex import PlexConnector

JPEG = b"\xff\xd8poster"


def _library(handler):  # type: ignore[no-untyped-def]
    http = ConnectorHttpClient("http://plex.lan:32400", transport=httpx.MockTransport(handler), retries=0)
    handle = ServiceHandle(service_id=UUID(int=7), name="Plex", config={}, secrets={"token": "t"}, http=http)
    return PlexConnector().provider("media.library", handle)


async def test_a_poster_comes_through_the_photo_transcoder() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/photo/:/transcode":
            return httpx.Response(200, content=JPEG, headers={"Content-Type": "image/jpeg"})
        # /thumb sends a poster kept on its original host elsewhere — refused by the client
        return httpx.Response(302, headers={"Location": "https://metadata-static.plex.tv/a/b.jpg"})

    assert await _library(handler).fetch_image("871178:1700000000") == JPEG
    asked = seen[-1].url
    assert asked.path == "/photo/:/transcode"
    assert asked.params["url"] == "/library/metadata/871178/thumb"
    assert asked.params["upscale"] == "0" and asked.params["minSize"] == "1"


async def test_a_picture_kept_on_another_host_is_not_an_outage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://image.tmdb.org/t/p/original/x.jpg"})

    with pytest.raises(ProviderNotFound):
        await _library(handler).fetch_image("42")
