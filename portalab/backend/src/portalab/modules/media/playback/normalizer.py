"""``SessionNormalizer`` (T022; R6): turns what any source reports into one ``PlaybackSession`` shape and
decides which event a change is worth — state changes always, progress at most every
``progressEventSeconds`` — so Plex, Jellyfin or a game launcher look the same downstream and the event
volume stays bounded."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from portalab.capabilities.media import SourcePlayback

ACTIVE = ("playing", "paused", "buffering")
CREDITS_LEEWAY_S = 30.0  # a position is read every few seconds: stopping as the credits begin still counts


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


def reached_end(
    position: float, duration: float | None, threshold: float | None, credits: float | None = None
) -> bool:
    """#101: the play reached its end — its end credits when the media server knows where they begin (a film
    stopped minutes before them is not finished, however long the credits), else the kind's threshold;
    explicit-only kinds (no threshold) never finish from a position."""
    if threshold is None:
        return False
    if credits is not None and credits > 0 and (not duration or credits < duration):
        return position >= credits - CREDITS_LEEWAY_S
    share = percent(position, duration)
    return share is not None and share >= threshold


def on_end(
    max_position: float, duration: float | None, threshold: float | None, credits: float | None = None
) -> str:
    """``finished`` once the end is reached (``reached_end``), else ``abandoned``."""
    if reached_end(max_position, duration, threshold, credits):
        return "media.playback_finished"
    return "media.playback_abandoned"
