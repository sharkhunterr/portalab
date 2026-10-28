"""Issue 265: a series' theme music as its media server gives it — a connector's answer comes wrapped."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Request

from portalab.capabilities.media import THEMES
from portalab.capabilities.results import Available
from portalab.modules.games.api.router import _audio


def test_a_theme_tune_in_the_ranges_asked() -> None:
    def request(value: str | None) -> Request:
        headers = [(b"range", value.encode())] if value else []
        return Request({"type": "http", "headers": headers})

    data = bytes(range(10))
    whole = _audio(data, request(None))
    assert whole.status_code == 200 and whole.body == data and whole.headers["accept-ranges"] == "bytes"
    part = _audio(data, request("bytes=2-4"))
    assert (
        part.status_code == 206 and part.body == data[2:5] and part.headers["content-range"] == "bytes 2-4/10"
    )
    assert _audio(data, request("bytes=7-")).body == data[7:]
    assert _audio(data, request("bytes=-3")).body == data[7:]


async def test_the_media_unwraps_the_theme() -> None:
    from portalab.capabilities.catalog import new_registry
    from portalab.modules.media.games import MediaGameSources

    class Plex:
        async def theme(self, external_id: str) -> Available[bytes]:
            return Available(b"ID3", datetime.now(UTC))

    capabilities = new_registry()
    capabilities.provide(THEMES, Plex(), instance_ref="svc", owner="test")
    sources = MediaGameSources(None, capabilities)  # type: ignore[arg-type]

    class Rows:
        def all(self) -> list[tuple[str, str]]:
            return [("svc", "42")]

    class Session:
        async def execute(self, _: object) -> Rows:
            return Rows()

        async def __aenter__(self) -> "Session":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    sources.database = type("DB", (), {"session": lambda self: Session()})()  # type: ignore[assignment]
    assert await sources.theme(uuid4()) == b"ID3"
