"""``SessionNormalizer`` (T022; R6): turns what any source reports into one ``PlaybackSession`` shape and
decides which event a change is worth — state changes always, progress at most every
``progressEventSeconds`` — so Plex, Jellyfin or a game launcher look the same downstream and the event
volume stays bounded."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from portalab.capabilities.media import SourcePlayback

ACTIVE = ("playing", "paused", "buffering")


@dataclass(frozen=True, slots=True)
class Decision:
    event: str | None  # playback event type to publish, or None
    state: str


def percent(position: float, duration: float | None) -> float | None:
    if not duration or duration <= 0:
        return None
    return round(min(1.0, max(0.0, position / duration)), 4)


def on_update(
    previous_state: str,
    last_event_at: datetime,
    now: datetime,
    report: SourcePlayback,
    progress_every: int,
) -> Decision:
    state = report.state
    if state == "stopped":
        return Decision(None, "stopped")  # ending is decided by ``on_end``
    if state == "paused" and previous_state != "paused":
        return Decision("media.playback_paused", state)
    if state in ("playing", "buffering") and previous_state in ("paused", "stale"):
        return Decision("media.playback_progressed", state)  # resume
    if now - last_event_at >= timedelta(seconds=max(1, progress_every)) and state == "playing":
        return Decision("media.playback_progressed", state)
    return Decision(None, state)


def on_end(max_position: float, duration: float | None, threshold: float | None) -> str:
    """``finished`` at/above the kind's threshold (explicit-only kinds never finish from a position)."""
    share = percent(max_position, duration)
    if threshold is not None and share is not None and share >= threshold:
        return "media.playback_finished"
    return "media.playback_abandoned"
