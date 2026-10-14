"""Issue 122: what a media server says, as service signals the automations watch — the plays under way
(Plex, Jellyfin, Tautulli…), how many are paused, and the title playing when there is one."""

from collections.abc import Sequence
from typing import Any

from portalab.capabilities.media import PLAYBACK, SourcePlayback
from portalab.capabilities.results import Available, CapabilityResult, Partial
from portalab.capabilities.service_signals import Signal, SignalRegistry, Value

OWNER = "module:media"


async def _sessions(provider: Any) -> Sequence[SourcePlayback] | None:
    try:
        found = await provider.now_playing()
    except Exception:
        return None  # the server did not answer: unknown, never « nobody plays »
    if isinstance(found, Available | Partial):  # a guarded provider says how it went
        found = found.value
    elif isinstance(found, CapabilityResult):
        return None  # stale or failed: what plays now is not known
    return list(found) if isinstance(found, list | tuple) else None


def register_media_signals(registry: SignalRegistry) -> None:
    async def playing(_service: str, provider: Any) -> Value | None:
        found = await _sessions(provider)
        return None if found is None else sum(1 for s in found if s.state != "stopped")

    async def paused(_service: str, provider: Any) -> Value | None:
        found = await _sessions(provider)
        return None if found is None else sum(1 for s in found if s.state == "paused")

    async def title(_service: str, provider: Any) -> Value | None:
        found = await _sessions(provider)
        if found is None:
            return None
        titles = sorted({s.title for s in found if s.state != "stopped"})
        return ", ".join(titles)[:200] if titles else "none"

    for key, kind, read, label, description in (
        ("media.plays", "number", playing, "Plays under way", "how many plays run now on the server"),
        ("media.plays_paused", "number", paused, "Plays paused", "how many plays are paused now"),
        ("media.playing_titles", "text", title, "Titles playing", "the titles playing now, « none » else"),
    ):
        registry.register(Signal(key, OWNER, PLAYBACK, kind, read, label=label, description=description))  # type: ignore[arg-type]
