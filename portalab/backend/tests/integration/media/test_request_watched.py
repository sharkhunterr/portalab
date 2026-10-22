"""A title someone asked for, watched by another member: ``media.request_watched`` for the asker — once per
request and viewer (a series' episodes count once), never for the asker's own plays, never in a replay."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import select, text

from portalab.capabilities.events import Envelope
from portalab.capabilities.media.testkit import library_record
from portalab.modules.media.models import MediaObject, MediaRequest
from portalab.modules.media.requests.watched import RequestWatched
from tests.integration.media.conftest import MediaHarness, users


@dataclass
class Ctx:
    replay: bool = False
    as_of: datetime = datetime(2026, 12, 1, tzinfo=UTC)

    async def idempotent_effect(self, key: str) -> bool:
        return True


def finished(viewer: str, object_id: str) -> Envelope:
    at = datetime(2026, 12, 1, 20, tzinfo=UTC)
    return Envelope(
        event_id=uuid4(),
        seq=0,
        type="media.playback_finished",
        type_version=1,
        occurred_at=at,
        received_at=at,
        source_system="test",
        source_event_id=None,
        actor_user_id=None,
        actor_kind="system",
        subject_type="user",
        subject_id=viewer,
        payload={"object": object_id, "kind": "episode"},
        provenance={},
        correlation_id=None,
    )


async def test_the_asker_is_told_once_per_viewer(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "jeremie", "thibaut")
    one = media.service(1)
    await media.module.library.upsert([library_record("201", title="Arcane", kind="series", year=2021)], one)
    now = datetime(2026, 11, 1, tzinfo=UTC)
    async with media.database.unit_of_work() as uow:
        series = (await uow.session.execute(select(MediaObject))).scalars().one()
        episode = MediaObject(
            id=uuid4(),
            kind="episode",
            title="Welcome to the Playground",
            sort_title="welcome",
            parent_id=series.id,
            status="active",
            available=True,
            effective={},
            field_provenance={},
            first_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        uow.session.add(episode)
        uow.session.add(
            MediaRequest(
                object_id=series.id,
                external_ref={"title": "Arcane", "kind": "series"},
                service_id=uuid4(),
                requester_user_id=people["jeremie"],
                state="available",
                source_state="available",
                counted="base",
                requested_at=now,
                updated_at=now,
            )
        )
    consumer = RequestWatched(media.database, media.ev.publisher)
    for _ in range(2):  # two episodes, or the same one twice: once
        await consumer.handle(finished(str(people["thibaut"]), str(episode.id)), Ctx())
    await consumer.handle(finished(str(people["jeremie"]), str(episode.id)), Ctx())  # their own play
    await consumer.handle(finished(str(uuid4()), str(episode.id)), Ctx(replay=True))  # a replay
    async with media.database.session() as session:
        told = (
            await session.execute(
                text("SELECT subject_id FROM events.events WHERE type = 'media.request_watched'")
            )
        ).all()
    assert [row[0] for row in told] == [str(people["jeremie"])]
