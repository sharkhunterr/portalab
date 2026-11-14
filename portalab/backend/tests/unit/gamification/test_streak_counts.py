"""Issues 415/416 — what keeps a play streak: the admin chooses finished plays only or interrupted ones too,
the radio, and the minimum length of a sitting; every kind of media counts. A play that reached its end (a
film, an episode, a book) counts whatever its length; an interrupted sitting, live TV, the radio and music
count from the minimum."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from portalab.capabilities.events import Envelope
from portalab.modules.gamification.streaks.service import counts, parse_streak

FINISHED, PARTIAL, RADIO = "media.playback_finished", "media.playback_abandoned", "media.radio_listened"


def event(kind_of_event: str, **payload: Any) -> Envelope:
    now = datetime(2026, 11, 14, tzinfo=UTC)
    return Envelope(
        event_id=uuid4(),
        seq=1,
        type=kind_of_event,
        type_version=1,
        occurred_at=now,
        received_at=now,
        source_system="portalab",
        source_event_id=None,
        actor_user_id=None,
        actor_kind="system",
        subject_type=None,
        subject_id=None,
        payload=payload,
        provenance={},
        correlation_id=None,
    )


FINISHED_ONLY = parse_streak({"event_types": [FINISHED], "min_watched_s": 1800})
EVERYTHING = parse_streak({"event_types": [FINISHED, PARTIAL, RADIO], "min_watched_s": 1800})


@pytest.mark.parametrize(
    ("config", "played", "counted"),
    [
        # finished plays only
        (FINISHED_ONLY, event(FINISHED, kind="episode", watched_s=1300), True),  # its end: any length
        (FINISHED_ONLY, event(FINISHED, kind="movie", watched_s=0.0), True),  # found finished later
        (FINISHED_ONLY, event(PARTIAL, kind="movie", watched_s=3000), False),  # 50 min, not finished
        (FINISHED_ONLY, event(PARTIAL, kind="live", watched_s=2400), True),  # live TV never finishes
        (FINISHED_ONLY, event(PARTIAL, kind="live", watched_s=600), False),
        (FINISHED_ONLY, event(FINISHED, kind="track", watched_s=200), False),  # a song: its time only
        (FINISHED_ONLY, event(RADIO, minutes=45, session="s"), False),  # the radio is not chosen
        # interrupted plays and the radio too, 30 minutes at least
        (EVERYTHING, event(PARTIAL, kind="movie", watched_s=3000), True),
        (EVERYTHING, event(PARTIAL, kind="book", watched_s=2000), True),
        (EVERYTHING, event(PARTIAL, kind="audiobook", watched_s=1000), False),
        (EVERYTHING, event(PARTIAL, kind="game", watched_s=3600), True),
        (EVERYTHING, event(RADIO, minutes=30, session="s"), True),
        (EVERYTHING, event(RADIO, minutes=5, session="s"), False),
        (EVERYTHING, event(FINISHED, kind="track", watched_s=2400), True),
        (EVERYTHING, event("media.request"), False),
    ],
)
def test_what_keeps_a_streak(config: Any, played: Envelope, counted: bool) -> None:
    assert counts(config, played) is counted


def test_an_action_without_a_length_counts_when_chosen() -> None:
    config = parse_streak({"event_types": ["user.signed_in"], "min_watched_s": 1800})
    assert counts(config, event("user.signed_in")) is True
