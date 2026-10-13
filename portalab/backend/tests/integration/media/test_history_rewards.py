"""#94 — a play recorded by a service's history counts for the progression when the live watch missed it:
``media.playback_finished`` (or ``abandoned`` with its minutes) is published once, for recent plays only,
never for a play the live watch saw end, never for an unlinked member."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI

from portalab.core.time import FixedClock
from portalab.modules.media.insights.rewards import HistoryRewards
from portalab.modules.media.models import Activity, PlaybackSession
from tests.integration.media.conftest import MediaHarness, users

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def _activity(user: Any, hours_ago: float, progress: float, **kw: Any) -> Activity:
    return Activity(
        service_id=uuid4(),
        ref=str(uuid4()),
        family="plex",
        priority=20,
        counted=True,
        external_user_id="1",
        user_id=user,
        kind="movie",
        title=kw.pop("title", "Spider-Man"),
        object_id=None,
        ids={},
        started_at=NOW - timedelta(hours=hours_ago),
        stopped_at=NOW - timedelta(hours=hours_ago - 2),
        watched_s=7200 * progress,
        duration_s=7200.0,
        progress=progress,
        received_at=NOW,
        **kw,
    )


async def test_finished_plays_from_history_count_once(app: FastAPI, media: MediaHarness) -> None:
    people = await users(app, media, "zoe")
    zoe = people["zoe"]
    async with media.database.unit_of_work() as uow:
        uow.session.add_all(
            [
                _activity(zoe, 5, 0.97, title="Finished yesterday"),
                _activity(zoe, 6, 0.30, title="Stopped early"),
                _activity(None, 5, 1.0, title="Someone unlinked"),
                _activity(zoe, 24 * 9, 1.0, title="Old history"),
                _activity(zoe, 10, 1.0, title="Seen live"),
                PlaybackSession(
                    session_key="live-1",
                    service_id=uuid4(),
                    user_id=zoe,
                    external_user_id="1",
                    kind="movie",
                    title="Seen live",
                    state="stopped",
                    position_s=7100.0,
                    max_position_s=7100.0,
                    duration_s=7200.0,
                    started_at=NOW - timedelta(hours=10),
                    updated_at=NOW - timedelta(hours=8),
                    as_of=NOW - timedelta(hours=8),
                    last_event_at=NOW - timedelta(hours=8),
                    state_seq=3,
                    ended=True,
                ),
            ]
        )
    rewards = HistoryRewards(
        media.database, media.module.history.events, media.module.threshold, clock=FixedClock(NOW)
    )
    assert await rewards.run() == 2  # the finished play, and the one stopped early (its minutes)
    assert await rewards.run() == 0  # once
    await media.dispatch()
    finished = [e for e in await media.events() if e[0] == "media.playback_finished"]
    assert len(finished) == 1 and finished[0][2] == str(zoe)
    assert finished[0][1]["session"].startswith("history:") and finished[0][1]["duration_s"] == 7200.0
    assert finished[0][1]["watched_s"] == 6984.0
    partial = [e for e in await media.events() if e[0] == "media.playback_abandoned"]
    assert [e[1]["watched_s"] for e in partial] == [2160.0]  # 30 % of 2 h
