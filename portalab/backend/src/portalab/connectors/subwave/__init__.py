"""``subwave`` connector (issue 168): SUB/WAVE, the homelab's AI radio — its live stream, what plays, and
asking its DJ for a song.

* ``media.radio``: ``GET /api/now-playing`` (the track on air, the DJ, the listeners, the stream's mount),
  ``GET /api/state`` (what comes next and what played), ``POST /api/request`` (a song, an artist or a vibe in
  plain words; the DJ resolves it in the background) then ``GET /api/request/{id}``, the live stream (the
  mount ``now-playing`` names, ``/stream.mp3`` by default) and a track's cover (``/api/cover/{id}``) — both
  relayed by the portal (a page served over HTTPS cannot play a plain-HTTP stream).
* ``service.health_probe``: ``GET /api/health`` (``{"status": "on-air"}``).

The station's listener endpoints are public on the local network: the connector only needs its address.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

from portalab.capabilities.connector_sdk import CapabilityBinding, ServiceHandle
from portalab.capabilities.health import HEALTH_PROBE
from portalab.capabilities.media import RADIO, RadioRequest, RadioState, RadioTrack, StreamBody
from portalab.capabilities.results import InvalidPayload, ProviderNotFound
from portalab.connectors.http_base import HttpConnector, binding, parse_time, safe_id

MAX_TRACKS = 10
STATUSES = {
    "pending": "pending",
    "processing": "pending",
    "queued": "queued",
    "matched": "queued",
    "done": "queued",
    "played": "queued",
    "playing": "queued",
    "failed": "failed",
    "rejected": "failed",
    "no_match": "failed",
    "error": "failed",
    "unknown": "unknown",
}


def _text(value: Any, limit: int = 200) -> str | None:
    return str(value).strip()[:limit] or None if isinstance(value, str | int | float) else None


def _is_health(status: Any) -> bool:
    """``/api/health``: ``{"status": "on-air"}`` (or ``{"onAir": true}`` for some releases)."""
    if not isinstance(status, Mapping):
        return False
    state = status.get("status")
    return "onAir" in status or (isinstance(state, str) and state.endswith("-air"))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Any]:
    return list(value)[:MAX_TRACKS] if isinstance(value, list) else []


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def map_track(row: Any) -> RadioTrack | None:
    """One track as SUB/WAVE tells it; ``None`` without a title."""
    if not isinstance(row, Mapping):
        return None
    title = _text(row.get("title"))
    if title is None:
        return None
    year = _number(row.get("year"))
    genres = row.get("genres")
    genre = _text(row.get("genre")) or (_text(genres[0]) if isinstance(genres, list) and genres else None)
    cover = row.get("subsonic_id") or row.get("id")
    return RadioTrack(
        title=title,
        artist=_text(row.get("artist")),
        album=_text(row.get("album")),
        year=int(year) if year else None,
        genre=genre.split(",")[0].strip() if genre else None,
        cover_ref=safe_id(cover) if isinstance(cover, str) and cover else None,
        started_at=parse_time(row.get("startedAt")) or parse_time(row.get("timestamp")),
        duration=_number(row.get("duration")),
        requested_by=_text(row.get("requestedBy"), 40),
    )


def map_request(answer: Any, fallback_id: str | None = None) -> RadioRequest:
    """What the station says of a request — whatever words it uses for its stages."""
    if not isinstance(answer, Mapping):
        raise InvalidPayload("not a SUB/WAVE request")
    raw = str(answer.get("status") or "").lower()
    if not raw:
        raw = "pending" if answer.get("success") is True else "failed"
    status = STATUSES.get(raw, "pending" if answer.get("success") is not False else "failed")
    ident = answer.get("requestId") or answer.get("id") or fallback_id
    return RadioRequest(
        id=safe_id(ident) if isinstance(ident, str | int) and str(ident) else None,
        status=status,
        detail=_text(answer.get("message") or answer.get("error") or answer.get("reason"), 280),
        track=map_track(answer.get("track") or answer.get("song")),
    )


class SubwaveConnector(HttpConnector):
    key = "subwave"
    name = "SUB/WAVE"
    description = "The homelab's radio: listen live, see what plays, ask its DJ for a song."
    icon = "radio"
    category = "media"
    secret_fields: frozenset[str] = frozenset()
    provides: Sequence[CapabilityBinding] = (binding(RADIO), binding(HEALTH_PROBE))
    status_path = "/api/health"
    public_path = "/api/health"

    def auth_headers(self, service: ServiceHandle) -> dict[str, str]:
        return {}

    def describe(self, status: Any) -> str:
        if not _is_health(status):
            raise InvalidPayload("not a SUB/WAVE health answer")
        return self.name

    def looks_like_us(self, public: Any) -> bool:
        return _is_health(public)

    def provider(self, capability: str, service: ServiceHandle) -> Any:
        if capability == RADIO:
            return SubwaveRadio(self, service)
        return super().provider(capability, service)


class SubwaveRadio:
    def __init__(self, connector: SubwaveConnector, service: ServiceHandle) -> None:
        self.connector, self.service = connector, service
        self.mount = "/stream.mp3"

    async def state(self) -> RadioState:
        now = await self.connector.get_json(self.service, "/api/now-playing")
        if not isinstance(now, Mapping):
            raise InvalidPayload("not a SUB/WAVE now-playing answer")
        try:
            more = await self.connector.get_json(self.service, "/api/state")
        except (ConnectionError, InvalidPayload, ProviderNotFound):
            more = {}
        state: Mapping[str, Any] = more if isinstance(more, Mapping) else {}
        stream = now.get("stream")
        mount = stream.get("mount") if isinstance(stream, Mapping) else None
        if isinstance(mount, str) and mount.startswith("/") and ".." not in mount:
            self.mount = mount
        dj = _mapping(now.get("dj"))
        station_info = _mapping(state.get("station"))
        listeners = now.get("listeners")
        context = _mapping(now.get("context"))
        current = map_track(state.get("current")) or map_track(now.get("nowPlaying"))
        history = _rows(state.get("history"))
        upcoming = _rows(state.get("upcoming"))
        return RadioState(
            station=_text(station_info.get("name")) or _text(dj.get("station")) or self.connector.name,
            on_air=now.get("streamOnline") is not False,
            current=current,
            upcoming=tuple(t for t in (map_track(r) for r in upcoming) if t),
            recent=tuple(t for t in (map_track(r) for r in history) if t),
            host=_text(dj.get("name"), 60),
            tagline=_text(dj.get("tagline"), 200),
            listeners=int(listeners["current"])
            if isinstance(listeners, Mapping) and isinstance(listeners.get("current"), int)
            else None,
            mood=_text(context.get("dominantMood"), 40),
        )

    async def ask(self, text: str, name: str) -> RadioRequest:
        try:
            answer = await self.connector.request(
                self.service, "POST", "/api/request", json_body={"text": text[:280], "name": name[:40]}
            )
        except ConnectionError as exc:
            # a refusal (too many requests, nobody listening, an empty text) is the station's answer
            return RadioRequest(id=None, status="failed", detail=str(exc)[:280])
        return map_request(answer)

    async def request_status(self, request_id: str) -> RadioRequest:
        ident = safe_id(request_id)
        try:
            answer = await self.connector.get_json(self.service, f"/api/request/{ident}")
        except ProviderNotFound:
            return RadioRequest(id=ident, status="unknown")
        return map_request(answer, ident)

    @asynccontextmanager
    async def listen(self) -> AsyncIterator[StreamBody]:
        async with self.connector._http(self.service).stream(
            "GET", self.mount, headers={"Accept-Encoding": "identity"}, read_timeout=30
        ) as response:
            if response.status_code >= 400:
                raise ConnectionError(f"the station answered HTTP {response.status_code}")
            yield StreamBody(
                status=200,
                content_type=response.headers.get("content-type") or "audio/mpeg",
                length=None,
                chunks=response.chunks,
            )

    async def cover(self, cover_ref: str) -> bytes:
        return await self.connector.get_bytes(self.service, f"/api/cover/{safe_id(cover_ref)}")
