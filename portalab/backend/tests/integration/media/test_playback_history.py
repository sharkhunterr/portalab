"""024 T021/T023 — sessions from two different sources are normalized identically; state changes emit
throttled events deduplicated by (session, state_seq); a lost source makes sessions stale then interrupted
with ``media.playback_error``; a session ending at/above the threshold is ``finished`` once, below is
``abandoned``; unlinked activity is never attributed; the history projection is idempotent, rebuilds
identically from the events, keeps ``finished`` sticky and resumes from the latest ``occurred_at`` across
sources; personal history is private."""

from datetime import timedelta

import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.media.testkit import library_record
from portalab.core.time import FixedClock
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration


async def kinds(media: MediaHarness) -> list[str]:
    return [e[0] for e in await media.events("media.playback")]


async def test_playback_lifecycle(app: FastAPI, media: MediaHarness, clock: FixedClock) -> None:
    people = await users(app, media, "alex")
    plex, jelly = media.service(1, "plex"), media.service(2, "jellyfin")
    await media.module.library.upsert(
        [library_record("m1", title="Alien", ids={"tmdb": "348"}, duration_s=6000)], plex
    )
    for svc in (plex, jelly):
        link = await media.module.links.claim(people["alex"], svc.service_id, f"alex@{svc.source_system[:4]}")
        await media.module.links.verify(None, link.id, None)
    a, b = media.playback(plex), media.playback(jelly)
    a.play(
        "s1",
        external_user_id="alex@plex",
        item_external_id="m1",
        kind="movie",
        position_s=10,
        duration_s=6000,
    )
    b.play(
        "x", external_user_id="alex@jell", ids={"tmdb": "348"}, kind="movie", position_s=5, duration_s=6000
    )
    b.play("anon", external_user_id="stranger", kind="movie", position_s=1, duration_s=100)
    await media.module.poller.tick()
    sessions = await media.module.poller.now_playing(people["alex"])
    assert {s.object_id for s in sessions} == {sessions[0].object_id} and len(sessions) == 2  # same object
    assert await kinds(media) == ["media.playback_started", "media.playback_started"]  # "anon" unattributed
    clock.advance(timedelta(seconds=20))
    a.play("s1", position_s=30)
    await media.module.poller.poll(plex.service_id, a)  # < 60 s since the last event: throttled
    a.play("s1", state="paused", position_s=40)
    await media.module.poller.poll(plex.service_id, a)
    clock.advance(timedelta(seconds=20))
    a.play("s1", state="playing", position_s=40)
    await media.module.poller.poll(plex.service_id, a)
    assert (await kinds(media))[2:] == ["media.playback_paused", "media.playback_progressed"]
    # Plex dies: stale, then interrupted after the timeout — never finished
    a.down = True
    await media.module.poller.poll(plex.service_id, a)
    async with media.database.session() as session:
        state = (
            await session.execute(
                text("SELECT state FROM media.playback_sessions WHERE session_key LIKE :k"), {"k": "%:s1"}
            )
        ).scalar_one()
    assert state == "stale"
    clock.advance(timedelta(seconds=200))
    await media.module.poller.poll(plex.service_id, a)
    assert (await kinds(media))[-1] == "media.playback_error"
    # Jellyfin session reaches 95 % then ends: finished once
    b.play("x", position_s=5700)
    await media.module.poller.poll(jelly.service_id, b)
    b.stop("x")
    await media.module.poller.poll(jelly.service_id, b)
    await media.module.poller.poll(jelly.service_id, b)
    assert (await kinds(media)).count("media.playback_finished") == 1
    async with media.database.session() as session:
        unlinked = (
            await session.execute(text("SELECT count(*) FROM media.playback_sessions WHERE user_id IS NULL"))
        ).scalar_one()
    assert unlinked == 1


async def test_history_projection(app: FastAPI, media: MediaHarness, clock: FixedClock) -> None:
    people = await users(app, media, "alex", "sam")
    svc = media.service(1)
    await media.module.library.upsert(
        [library_record("m1", title="Alien", ids={"tmdb": "348"}, duration_s=1000)], svc
    )
    link = await media.module.links.claim(people["alex"], svc.service_id, "alex")
    await media.module.links.verify(None, link.id, None)
    fake = media.playback(svc)
    fake.play("s1", external_user_id="alex", item_external_id="m1", position_s=100, duration_s=1000)
    await media.module.poller.tick()
    clock.advance(timedelta(seconds=90))
    fake.play("s1", position_s=300)
    await media.module.poller.poll(svc.service_id, fake)
    fake.stop("s1")
    await media.module.poller.poll(svc.service_id, fake)  # 30 % → abandoned → resume available
    await media.dispatch()
    resume = await media.module.history.continue_items(people["alex"])
    assert len(resume) == 1 and resume[0][0].resume_position_s == 300 and resume[0][0].state == "in_progress"
    assert "media.resume_available" in [e[0] for e in await media.events("media.resume")]
    clock.advance(timedelta(hours=1))
    fake.play("s2", external_user_id="alex", item_external_id="m1", position_s=950, duration_s=1000)
    await media.module.poller.poll(svc.service_id, fake)
    fake.stop("s2")
    await media.module.poller.poll(svc.service_id, fake)
    await media.dispatch()
    async with media.database.session() as session:
        before = sorted(
            tuple(r)
            for r in await session.execute(
                text(
                    "SELECT event_id, kind, completed, position_to_s"
                    " FROM media.history_entries ORDER BY event_id"
                )
            )
        )
        progress = (await session.execute(text("SELECT state, percent FROM media.user_progress"))).one()
    assert progress[0] == "finished" and await media.module.history.continue_items(people["alex"]) == []
    # an older progress event arriving late never reverts "finished"
    from uuid import uuid4

    await media.module.history.apply(
        event_id=uuid4(),
        event_type="media.playback_progressed",
        user=people["alex"],
        object_id=resume[0][1].id,
        payload={"position_s": 10, "duration_s": 1000, "session": "late"},
        occurred_at=clock.now() - timedelta(days=1),
        live=False,
    )
    async with media.database.session() as session:
        assert (
            await session.execute(text("SELECT state FROM media.user_progress"))
        ).scalar_one() == "finished"
    # rebuild from the event log: identical rows, no duplicates, nothing re-emitted
    async with media.database.unit_of_work() as uow:
        await uow.session.execute(text("DELETE FROM media.history_entries"))
        await uow.session.execute(text("DELETE FROM media.user_progress"))
    for envelope in await _playback_envelopes(media):
        await media.module.history.handle(envelope, _Replay())
        await media.module.history.handle(envelope, _Replay())  # redelivery is a no-op
    async with media.database.session() as session:
        after = sorted(
            tuple(r)
            for r in await session.execute(
                text(
                    "SELECT event_id, kind, completed, position_to_s"
                    " FROM media.history_entries ORDER BY event_id"
                )
            )
        )
        assert (
            await session.execute(text("SELECT state FROM media.user_progress"))
        ).scalar_one() == "finished"
    assert before == after
    # private by default: another user's reader view is empty
    from portalab.core.authz_port import Principal

    assert await media.module.history_reader.for_user(people["alex"], Principal(user_id=people["sam"])) == []
    assert await media.module.history_reader.for_user(people["alex"], Principal(user_id=people["alex"]))


class _Replay:
    replay = True
    as_of = None

    async def idempotent_effect(self, key: str) -> bool:
        return False


async def _playback_envelopes(media: MediaHarness) -> list:
    from portalab.capabilities.events import Envelope

    async with media.database.session() as session:
        rows = await session.execute(
            text(
                "SELECT event_id, seq, type, occurred_at, received_at, subject_type, subject_id, payload"
                " FROM events.events WHERE type LIKE 'media.playback%' ORDER BY seq"
            )
        )
        return [
            Envelope(
                event_id=r[0],
                seq=r[1],
                type=r[2],
                type_version=1,
                occurred_at=r[3],
                received_at=r[4],
                source_system="media",
                source_event_id=None,
                actor_user_id=None,
                actor_kind="system",
                subject_type=r[5],
                subject_id=r[6],
                payload=dict(r[7]),
                provenance={},
                correlation_id=None,
            )
            for r in rows
        ]
