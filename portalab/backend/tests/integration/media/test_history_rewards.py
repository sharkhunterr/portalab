"""#94 — a play recorded by a service's history counts for the progression when the live watch missed it:
``media.playback_finished`` (or ``abandoned`` with its minutes) is published once, for recent plays only,
never for a play the live watch saw end, never for an unlinked member. #101: a play the live watch followed
to its stop keeps the live verdict (a history's rounded 90 % is not a finished film), and the end credits,
where the media server marks them, decide whether a play reached its end."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI

from portalab.core.time import FixedClock
from portalab.modules.media.insights.rewards import HistoryRewards
from portalab.modules.media.models import Activity, MediaObject, PlaybackSession, UserLink
from tests.integration.media.conftest import MediaHarness, users

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
LIVE, LINKED_LATE = uuid4(), uuid4()  # a Plex followed live, linked a month ago — and one linked today


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
    live_service = uuid4()
    async with media.database.unit_of_work() as uow:
        uow.session.add_all(
            [
                _link(zoe, live_service, NOW - timedelta(days=30)),
                _activity(zoe, 5, 0.97, title="Finished yesterday"),
                _activity(zoe, 6, 0.30, title="Stopped early"),
                _activity(None, 5, 1.0, title="Someone unlinked"),
                _activity(zoe, 24 * 9, 1.0, title="Old history"),
                _activity(zoe, 10, 1.0, title="Seen live"),
                PlaybackSession(
                    session_key="live-1",
                    service_id=live_service,
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


def _link(user: Any, service: UUID, at: datetime) -> UserLink:
    return UserLink(user_id=user, service_id=service, external_user_id="1", verified=True, created_at=at)


def _live(
    user: Any, film: UUID, key: str, start: datetime, stop: datetime, at: float, **kw: Any
) -> PlaybackSession:
    return PlaybackSession(
        session_key=key,
        object_id=film,
        service_id=kw.pop("service", LIVE),
        user_id=user,
        external_user_id="1",
        kind="movie",
        title="?",
        state=kw.pop("state", "stopped"),
        position_s=at,
        max_position_s=at,
        start_position_s=kw.pop("start_at", 0.0),
        duration_s=8700.0,
        started_at=start,
        updated_at=stop,
        as_of=stop,
        last_event_at=stop,
        state_seq=3,
        ended=True,
    )


async def _film(media: MediaHarness, title: str) -> UUID:
    object_id = uuid4()
    async with media.database.unit_of_work() as uow:
        uow.session.add(
            MediaObject(
                id=object_id,
                kind="movie",
                title=title,
                sort_title=title.lower(),
                available=True,
                effective={},
                field_provenance={},
                status="active",
                first_seen_at=NOW,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    return object_id


async def test_the_live_verdict_stands_and_the_end_credits_decide(app: FastAPI, media: MediaHarness) -> None:
    people = await users(app, media, "yann")
    yann = people["yann"]
    start, stop = NOW - timedelta(hours=3), NOW - timedelta(hours=2, minutes=47)
    titles = ("Brand New Day", "Cut off", "Before the credits", "Into the credits", "Before the link")
    films = {title: await _film(media, title) for title in titles}

    def played(title: str, progress: float) -> Activity:
        row = _activity(yann, 3, progress, title=title)
        row.object_id, row.started_at, row.stopped_at = films[title], start, stop
        row.duration_s, row.watched_s = 8700.0, 754.0
        return row

    async with media.database.unit_of_work() as uow:
        uow.session.add_all(
            [
                _link(yann, LIVE, NOW - timedelta(days=30)),
                _link(yann, LINKED_LATE, NOW - timedelta(hours=1)),
                # followed live to a stop at 89.5 %: the history's rounded 90 % does not finish it, nor
                # count its minutes a second time
                played("Brand New Day", 0.90),
                _live(yann, films["Brand New Day"], "live-bnd", start, stop + timedelta(seconds=16), 7790.0),
                # a live session cut off (the source stopped answering): the history decides
                played("Cut off", 0.99),
                _live(yann, films["Cut off"], "live-cut", start, stop, 4000.0, state="interrupted"),
                # unseen live, stopped before the end credits (93.5 %): not finished
                played("Before the credits", 0.92),
                # unseen live, into the end credits: finished
                played("Into the credits", 0.94),
                # #102: followed live before the account was linked: nothing published then — it counts now
                played("Before the link", 0.99),
                _live(yann, films["Before the link"], "live-late", start, stop, 8600.0, service=LINKED_LATE),
            ]
        )
    credits = {films["Before the credits"]: 8136.0, films["Into the credits"]: 8136.0}

    async def credits_start(object_id: UUID) -> float | None:
        return credits.get(object_id)

    rewards = HistoryRewards(
        media.database,
        media.module.history.events,
        media.module.threshold,
        credits=credits_start,
        clock=FixedClock(NOW),
    )
    assert await rewards.run() == 4
    await media.dispatch()
    named = {v: k for k, v in films.items()}
    by_title = {named[UUID(e[1]["object"])]: e[0] for e in await media.events("media.playback")}
    assert by_title == {
        "Cut off": "media.playback_finished",
        "Before the credits": "media.playback_abandoned",
        "Into the credits": "media.playback_finished",
        "Before the link": "media.playback_finished",
    }


async def test_a_play_from_another_history_is_no_play_followed(app: FastAPI, media: MediaHarness) -> None:
    """#340: Plex's own history leaves a stopped session without minutes beside the play — Tautulli's play of
    it is no play the live watch followed: it counts."""
    people = await users(app, media, "noe")
    noe = people["noe"]
    film = await _film(media, "Deadlock")
    start, stop = NOW - timedelta(hours=3), NOW - timedelta(hours=1)
    row = _activity(noe, 3, 1.0, title="Deadlock")
    row.object_id, row.started_at, row.stopped_at = film, start, stop
    history = _live(noe, film, f"{LIVE}:history:870805:{stop.isoformat()}", stop, stop, 0.0)
    history.duration_s = None
    async with media.database.unit_of_work() as uow:
        uow.session.add_all([_link(noe, LIVE, NOW - timedelta(days=30)), row, history])
    rewards = HistoryRewards(
        media.database, media.module.history.events, media.module.threshold, clock=FixedClock(NOW)
    )
    assert await rewards.run() == 1
    await media.dispatch()
    assert [e[0] for e in await media.events("media.playback")] == ["media.playback_finished"]


async def test_the_catch_up_reaches_back_to_the_account_s_link(app: FastAPI, media: MediaHarness) -> None:
    """#341: an outage of days loses no play lived after the account's link (48 h of grace before it), at most
    30 days back; without a link, only the last 48 hours."""
    people = await users(app, media, "eva")
    eva = people["eva"]
    history = uuid4()

    def play(title: str, days: float, *, service: UUID = history) -> Activity:
        row = _activity(eva, 24 * days, 1.0, title=title)
        row.service_id = service
        return row

    async with media.database.unit_of_work() as uow:
        uow.session.add_all(
            [
                _link(eva, history, NOW - timedelta(days=10)),
                play("After the link", 5),
                play("Just before the link", 11),
                play("Long before the link", 13),
                play("Unlinked account, old", 5, service=uuid4()),
                play("Unlinked account, recent", 1, service=uuid4()),
            ]
        )
    rewards = HistoryRewards(
        media.database, media.module.history.events, media.module.threshold, clock=FixedClock(NOW)
    )
    assert await rewards.run() == 3
    later = HistoryRewards(
        media.database,
        media.module.history.events,
        media.module.threshold,
        clock=FixedClock(NOW + timedelta(days=40)),
    )
    async with media.database.unit_of_work() as uow:
        uow.session.add(play("Forgotten for 31 days", -9))
    assert await later.run() == 0  # 31 days back: too far


async def test_the_plays_in_the_last_minutes_before_the_credits_are_finished_on_review(
    app: FastAPI, media: MediaHarness
) -> None:
    """#342: two minutes before the end credits finish a play (it was 30 s) — the review publishes the finish
    of the plays judged abandoned that reach it now, followed live or read from a history, once, without
    minutes."""
    people = await users(app, media, "tom")
    tom = people["tom"]
    titles = ("Live, a minute short", "Live, long before", "History, a minute short", "Threshold only")
    films = {title: await _film(media, title) for title in titles}
    start, stop = NOW - timedelta(hours=5), NOW - timedelta(hours=3)

    def played(title: str, progress: float) -> Activity:
        row = _activity(tom, 5, progress, title=title)
        row.object_id, row.started_at, row.stopped_at, row.duration_s = films[title], start, stop, 8700.0
        row.rewarded_at = stop  # judged then: abandoned
        return row

    async with media.database.unit_of_work() as uow:
        uow.session.add_all(
            [
                _link(tom, LIVE, NOW - timedelta(days=30)),
                _live(tom, films["Live, a minute short"], "live-short", start, stop, 8050.0),
                _live(tom, films["Live, long before"], "live-long", start, stop, 7500.0),
                played("History, a minute short", 0.93),
                played("Threshold only", 0.95),  # no credits marker: the 90 % threshold decided already
            ]
        )
    credits = {films[t]: 8136.0 for t in titles[:3]}

    async def credits_start(object_id: UUID) -> float | None:
        return credits.get(object_id)

    rewards = HistoryRewards(
        media.database,
        media.module.history.events,
        media.module.threshold,
        credits=credits_start,
        clock=FixedClock(NOW),
    )
    since = {"since": (NOW - timedelta(days=1)).isoformat()}
    assert await rewards.review_endings(since) == 2
    assert await rewards.review_endings(since) == 0  # once
    await media.dispatch()
    named = {v: k for k, v in films.items()}
    finished = {named[UUID(e[1]["object"])]: e[1]["watched_s"] for e in await media.events("media.playback")}
    assert finished == {"Live, a minute short": 0.0, "History, a minute short": 0.0}
