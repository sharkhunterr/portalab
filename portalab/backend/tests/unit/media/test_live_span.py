"""Issue 417 — a live TV sitting's time runs from its first piece's start to its last piece's end (a channel
of short programmes counts its whole evening), never less than its pieces tell."""

from datetime import UTC, datetime, timedelta

from portalab.modules.media.insights.rewards import span
from portalab.modules.media.models import Activity

START = datetime(2026, 11, 13, 17, 54, tzinfo=UTC)


def piece(minute: float, watched: float, *, ended: float | None = None) -> Activity:
    start = START + timedelta(minutes=minute)
    stop = None if ended is None else START + timedelta(minutes=ended)
    return Activity(kind="live", started_at=start, stopped_at=stop, watched_s=watched)


def test_a_sitting_counts_from_its_first_start_to_its_last_end() -> None:
    evening = [
        piece(0, 190, ended=3),
        piece(3, 142, ended=6),
        piece(7, 153, ended=9),
        piece(32, 162, ended=35),
    ]
    assert span(evening) == 35 * 60  # 35 minutes, not the 647 s Plex tells


def test_never_less_than_the_pieces_tell() -> None:
    assert span([piece(0, 400, ended=2)]) == 400
    assert span([piece(0, 120)]) == 120  # no known end: its own minutes
