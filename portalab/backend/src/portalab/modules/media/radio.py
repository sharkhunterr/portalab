"""The homelab's radio (issue 168): what a ``media.radio`` station plays, its live stream and covers
relayed by the portal, and asking its DJ for a song in the member's name (their display name on air).

A member asks at most once every ``ASK_EVERY`` seconds here (the station also limits its listeners)."""

import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any
from uuid import UUID

from portalab.capabilities.dashboard import Refresh, Size, SizeLimits, WidgetDefinition, WidgetPayload
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.media import (
    RADIO,
    RadioRequest,
    RadioState,
    RadioStation,
    RadioTrack,
    StreamBody,
    unwrap,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.errors import PortalError, Unavailable
from portalab.core.time import Clock, utc_now
from portalab.modules.media.permissions import MEDIA_PLAY

ASK_EVERY = 20


class RadioUnavailable(Unavailable):
    default_code = "media.radio_unavailable"
    default_title = "The radio is not available"


class RadioAskedTooSoon(PortalError):
    status = 429
    default_code = "media.radio_too_soon"
    default_title = "One request at a time"


def track_out(track: RadioTrack | None) -> dict[str, Any] | None:
    if track is None:
        return None
    out = asdict(track)
    out["started_at"] = track.started_at.isoformat() if track.started_at else None
    return out


def request_out(request: RadioRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "status": request.status,
        "detail": request.detail,
        "track": track_out(request.track),
    }


class RadioService:
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities
        self._asked: dict[UUID, float] = {}

    def station(self) -> RadioStation | None:
        try:
            providers = self.capabilities.system_providers(RADIO)
        except Exception:
            return None
        return providers[0].provider if providers else None

    def _station(self) -> RadioStation:
        station = self.station()
        if station is None:
            raise RadioUnavailable("No radio is connected.")
        return station

    async def state(self) -> dict[str, Any]:
        station = self.station()
        if station is None:
            return {"available": False}
        try:
            state: RadioState = unwrap(await station.state())  # wrapped by the capability layer
        except Exception as exc:
            raise RadioUnavailable("The radio does not answer right now.") from exc
        return {
            "available": True,
            "station": state.station,
            "on_air": state.on_air,
            "host": state.host,
            "tagline": state.tagline,
            "listeners": state.listeners,
            "mood": state.mood,
            "current": track_out(state.current),
            "upcoming": [track_out(t) for t in state.upcoming],
            "recent": [track_out(t) for t in state.recent],
        }

    async def _name(self, user: UUID) -> str:
        try:
            providers = self.capabilities.system_providers(DIRECTORY)
            summary = await providers[0].provider.get_user_summary(user) if providers else None
        except Exception:
            summary = None
        return (summary.display_name if summary is not None and summary.display_name else "anon")[:40]

    async def ask(self, user: UUID, text: str) -> dict[str, Any]:
        station = self._station()
        now = time.monotonic()
        last = self._asked.get(user)
        if last is not None and now - last < ASK_EVERY:
            raise RadioAskedTooSoon(
                "Wait a moment before asking again.",
                extensions={"retry_after": int(ASK_EVERY - (now - last)) + 1},
            )
        self._asked[user] = now
        try:
            answer = unwrap(await station.ask(text.strip()[:280], await self._name(user)))
        except Exception as exc:
            raise RadioUnavailable("The radio does not answer right now.") from exc
        return request_out(answer)

    async def request_status(self, request_id: str) -> dict[str, Any]:
        try:
            return request_out(unwrap(await self._station().request_status(request_id)))
        except RadioUnavailable:
            raise
        except Exception as exc:
            raise RadioUnavailable("The radio does not answer right now.") from exc

    @asynccontextmanager
    async def listen(self) -> AsyncIterator[StreamBody]:
        try:
            opened = self._station().listen()
            body = await opened.__aenter__()
        except RadioUnavailable:
            raise
        except Exception as exc:
            raise RadioUnavailable("The radio stream cannot be reached.") from exc
        try:
            yield body
        finally:
            await opened.__aexit__(None, None, None)

    async def cover(self, cover_ref: str) -> bytes:
        try:
            data: bytes = unwrap(await self._station().cover(cover_ref))
            return data
        except RadioUnavailable:
            raise
        except Exception as exc:
            raise RadioUnavailable("No cover for this track.") from exc


# --- the dashboard's widget --------------------------------------------------------------------------------
RADIO_WIDGET = WidgetDefinition(
    key="media.radio",
    owner="module:media",
    title_key="media:widget.radio.title",
    description_key="media:widget.radio.description",
    icon="radio",
    required_permission=MEDIA_PLAY,
    size=SizeLimits(default=Size(6, 2), min=Size(3, 1), max=Size(12, 4)),
    refresh=Refresh(mode="interval", interval_s=30),
    stale_after_s=120,
    component_id="media.radio",
)


class RadioWidget:
    """Issue 168: the radio on the dashboard — what plays, listen, ask for a song."""

    def __init__(self, radio: RadioService, clock: Clock | None = None) -> None:
        self.radio, self.clock = radio, clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        if self.radio.station() is None:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        try:
            state = await self.radio.state()
        except RadioUnavailable:
            return WidgetPayload("unavailable", as_of=utc_now(self.clock))
        return WidgetPayload("available", as_of=utc_now(self.clock), data=state)
