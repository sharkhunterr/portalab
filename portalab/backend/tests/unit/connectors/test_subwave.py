"""Issue 168 — SUB/WAVE answers read into the portal's radio: the track on air, what played, the DJ, the
listeners; a request's stages whatever words the station uses; and the radio service asking in the member's
name, at most once every 20 seconds."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from portalab.capabilities.media import RADIO, SPECS, RadioRequest, RadioState, StreamBody
from portalab.capabilities.registry import CapabilityRegistry
from portalab.connectors.subwave import SubwaveConnector, map_request, map_track
from portalab.core.errors import NotFound
from portalab.modules.media.radio import RadioAskedTooSoon, RadioService


def test_tracks_and_requests_are_read() -> None:
    track = map_track(
        {
            "subsonic_id": "1RRQ2JvWbIb8ntrkguQzMq",
            "title": "Way of the World",
            "artist": "Genesis",
            "album": "We Can't Dance",
            "genre": "Art Rock, Pop",
            "year": 1991,
            "duration": 340,
            "requestedBy": "Alice",
            "startedAt": "2026-10-21T08:10:02.696Z",
        }
    )
    assert track is not None and track.title == "Way of the World" and track.genre == "Art Rock"
    assert (
        track.cover_ref == "1RRQ2JvWbIb8ntrkguQzMq" and track.year == 1991 and track.requested_by == "Alice"
    )
    assert map_track({"artist": "nobody"}) is None
    assert map_request({"success": True, "requestId": "r1"}).status == "pending"
    assert map_request({"status": "queued", "id": "r1", "track": {"title": "Alive"}}).track is not None
    refused = map_request({"success": False, "message": "Empty request"})
    assert refused.status == "failed" and refused.detail == "Empty request"
    assert map_request({"status": "unknown"}, "r9") == RadioRequest(id="r9", status="unknown")
    connector = SubwaveConnector()  # its health answer, whatever the release
    assert connector.looks_like_us({"status": "on-air"}) and connector.looks_like_us({"onAir": True})
    assert not connector.looks_like_us({"status": "ok"})


class _Station:
    def __init__(self) -> None:
        self.asked: list[tuple[str, str]] = []

    async def state(self) -> RadioState:
        return RadioState(station="Retro Rock", on_air=True, host="Gus", listeners=2)

    async def ask(self, text: str, name: str) -> RadioRequest:
        self.asked.append((text, name))
        return RadioRequest(id="r1", status="pending")

    async def request_status(self, request_id: str) -> RadioRequest:
        return RadioRequest(id=request_id, status="queued")

    @asynccontextmanager
    async def listen(self) -> AsyncIterator[StreamBody]:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"ID3"

        yield StreamBody(status=200, content_type="audio/mpeg", length=None, chunks=chunks())

    async def cover(self, cover_ref: str) -> bytes:
        return b"jpeg"


async def test_the_radio_service() -> None:
    registry = CapabilityRegistry()
    registry.declare(next(spec for spec in SPECS if spec.name == RADIO))
    service = RadioService(registry)
    assert await service.state() == {"available": False}
    station = _Station()
    registry.provide(RADIO, station, instance_ref="subwave", owner="test")
    state = await service.state()
    assert state["station"] == "Retro Rock" and state["host"] == "Gus" and state["listeners"] == 2
    member = uuid4()
    assert (await service.ask(member, "  something calm  "))["status"] == "pending"
    assert station.asked == [("something calm", "anon")]  # no directory: credited « anon »
    with pytest.raises(RadioAskedTooSoon):
        await service.ask(member, "again")
    someone = uuid4()
    assert (await service.ask(someone, "another member"))["id"] == "r1"
    assert (await service.request_status("r1", someone))["status"] == "queued"
    with pytest.raises(NotFound):  # #280: a member follows only their own requests
        await service.request_status("r1", member)
    async with service.listen() as body:
        assert [chunk async for chunk in body.chunks] == [b"ID3"]
