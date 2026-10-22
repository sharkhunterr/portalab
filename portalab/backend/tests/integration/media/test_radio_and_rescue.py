"""Issue 227 — the radio listened to in the portal's player counts, by the server, in slices of a quarter of
an hour of stream relayed (never told by the page), and a song taken by the DJ is an event of its own.
Issue 228 — a title about to be deleted (Maintainerr), played to the end: ``media.leaving_watched`` for who
played it, once per member and title (an episode rescues its series), never in a replay."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, text

from portalab.capabilities.events import Envelope
from portalab.capabilities.media import RADIO, RadioRequest, RadioState
from portalab.capabilities.media.testkit import library_record
from portalab.modules.media.models import MediaObject
from portalab.modules.media.requests.watched import LeavingWatched
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users

pytestmark = pytest.mark.integration


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


async def published(media: MediaHarness, name: str) -> list[tuple[str, dict[str, Any]]]:
    async with media.database.session() as session:
        rows = (
            await session.execute(
                text("SELECT subject_id, payload FROM events.events WHERE type = :t ORDER BY seq"),
                {"t": name},
            )
        ).all()
    return [(row[0], dict(row[1])) for row in rows]


class Cleanup:
    def __init__(self, leaving: list[Any]) -> None:
        self.entries = leaving

    def configured(self) -> bool:
        return True

    async def leaving(self) -> list[Any]:
        return self.entries


async def test_a_title_leaving_watched_is_rescued_once(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness
) -> None:
    people = await users(app, media, "lea", "noe")
    one = media.service(1)
    await media.module.library.upsert([library_record("301", title="Dark", kind="series", year=2017)], one)
    now = datetime(2026, 11, 1, tzinfo=UTC)
    async with media.database.unit_of_work() as uow:
        series = (await uow.session.execute(select(MediaObject))).scalars().one()
        episode = MediaObject(
            id=uuid4(),
            kind="episode",
            title="Secrets",
            sort_title="secrets",
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
    soon = now + timedelta(days=3)
    leaving = [SimpleNamespace(object_id=series.id, item=SimpleNamespace(kind="series", delete_at=soon))]
    consumer = LeavingWatched(media.database, media.ev.publisher, Cleanup(leaving))
    for _ in range(2):  # two episodes of the same series: rescued once
        await consumer.handle(finished(str(people["lea"]), str(episode.id)), Ctx())
    await consumer.handle(finished(str(people["noe"]), str(episode.id)), Ctx())  # another member: theirs too
    await consumer.handle(finished(str(uuid4()), str(episode.id)), Ctx(replay=True))  # a replay: never
    await consumer.handle(finished(str(people["lea"]), str(uuid4())), Ctx())  # a title not leaving
    told = await published(media, "media.leaving_watched")
    assert [who for who, _ in told] == [str(people["lea"]), str(people["noe"])]
    assert told[0][1] == {"object": str(series.id), "kind": "series", "delete_at": soon.isoformat()}


class _Station:
    async def state(self) -> RadioState:
        return RadioState(station="Retro Rock", on_air=True)

    async def ask(self, text: str, name: str) -> RadioRequest:
        return RadioRequest(id="r1", status="pending")

    async def request_status(self, request_id: str) -> RadioRequest:
        return RadioRequest(id=request_id, status="queued")

    def listen(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def cover(self, cover_ref: str) -> bytes:
        return b""


async def test_a_song_asked_is_an_event(app: FastAPI, client: httpx.AsyncClient, media: MediaHarness) -> None:
    people = await users(app, media, "uma")
    media.module.capabilities.provide(RADIO, _Station(), instance_ref="test", owner="test")
    media.module.radio._asked.clear()
    await login(client, "uma")
    asked = await client.post("/api/v1/media/radio/requests", json={"text": "Daft Punk"})
    assert asked.status_code == 200, asked.text
    assert await published(media, "media.radio_requested") == [(str(people["uma"]), {"request": "r1"})]


async def test_listening_counted_by_slices(media: MediaHarness, app: FastAPI) -> None:
    people = await users(app, media, "ivy")
    user: UUID = people["ivy"]
    for slice_ in (1, 2, 2):  # the same slice twice (a retry): once
        await media.module.radio.listened(user, "s1", slice_)
    told = await published(media, "media.radio_listened")
    assert [payload["slice"] for _, payload in told] == [1, 2]
    assert told[0] == (str(user), {"minutes": 15, "session": "s1", "slice": 1})
