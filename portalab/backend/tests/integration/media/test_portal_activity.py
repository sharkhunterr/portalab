"""#282 — a book read or an audiobook listened to in the portal counts in the member's statistics: each
ended sitting becomes an activity row of theirs (time spent, progress, the work), once — a replay changes
nothing — never rewarded twice, never for a play a service's history told already, never without time."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.events import Envelope
from portalab.capabilities.media.testkit import library_record
from portalab.core.time import FixedClock
from portalab.modules.media.insights.portal import PortalActivity
from portalab.modules.media.models import Activity, MediaObject
from tests.integration.identity.helpers import login
from tests.integration.media.conftest import MediaHarness, users


@dataclass
class Ctx:
    replay: bool = False
    as_of: datetime = datetime(2026, 10, 29, tzinfo=UTC)

    async def idempotent_effect(self, key: str) -> bool:
        return True


def ended(
    user: UUID, at: datetime, payload: dict[str, Any], kind: str = "media.playback_abandoned"
) -> Envelope:
    return Envelope(
        event_id=uuid4(),
        seq=0,
        type=kind,
        type_version=1,
        occurred_at=at,
        received_at=at,
        source_system="media",
        source_event_id=None,
        actor_user_id=None,
        actor_kind="system",
        subject_type="user",
        subject_id=str(user),
        payload=payload,
        provenance={},
        correlation_id=None,
    )


async def test_sittings_in_the_portal_count_in_the_statistics(
    app: FastAPI, client: httpx.AsyncClient, media: MediaHarness, clock: FixedClock
) -> None:
    zoe = (await users(app, media, "zoe"))["zoe"]
    grimmory = media.service(1)
    await media.module.library.upsert(
        [
            library_record("a1", title="Alien - Le fleuve des souffrances", kind="audiobook", year=2026),
            library_record("b1", title="Dracula", kind="book", year=1897),
        ],
        grimmory,
    )
    async with media.database.unit_of_work() as uow:
        objects = {o.title: o.id for o in (await uow.session.execute(select(MediaObject))).scalars()}
    alien, dracula = objects["Alien - Le fleuve des souffrances"], objects["Dracula"]
    now = clock.now()
    service = str(grimmory.service_id)
    portal = PortalActivity(media.database, clock=clock)

    def sitting(object_id: UUID, **payload: Any) -> dict[str, Any]:
        return {"object": str(object_id), "service": service, "session": uuid4().hex, **payload}

    listened = ended(
        zoe,
        now - timedelta(hours=1),
        sitting(alien, kind="audiobook", via="portal", watched_s=1883.8, duration_s=36000.0, percent=0.54),
    )
    await portal.handle(listened, Ctx())
    await portal.handle(listened, Ctx(replay=True))  # a replay stores nothing more
    # a book read before ``via`` was sent: its position is the time spent reading
    await portal.handle(
        ended(zoe, now - timedelta(hours=3), sitting(dracula, kind="book", position_s=900.0, percent=0.1)),
        Ctx(),
    )
    # never: a play a history told (already in the activity), a sitting with no time, a film's live play
    await portal.handle(
        ended(zoe, now, {**sitting(alien, kind="audiobook", watched_s=600.0), "session": "history:x"}), Ctx()
    )
    await portal.handle(ended(zoe, now, sitting(dracula, kind="book", via="portal", watched_s=0.0)), Ctx())
    await portal.handle(ended(zoe, now, sitting(alien, kind="movie", watched_s=600.0)), Ctx())

    async with media.database.session() as session:
        rows = {r.kind: r for r in (await session.execute(select(Activity))).scalars()}
    assert set(rows) == {"audiobook", "book"}
    heard = rows["audiobook"]
    assert heard.user_id == zoe and heard.work_id == alien and heard.service_id == grimmory.service_id
    assert heard.watched_s == 1883.8 and heard.progress == 0.54 and heard.platform == "Portalab"
    assert heard.started_at == now - timedelta(hours=1, seconds=1883.8)
    assert heard.rewarded_at is not None  # its own events gave its XP: the history rewards skip it
    assert rows["book"].watched_s == 900.0

    while await media.module.aggregator.run():
        pass
    await login(client, "zoe")
    mine = (await client.get("/api/v1/media/insights", params={"period": "30d"})).json()
    assert mine["totals"]["plays"] == 2 and mine["totals"]["seconds"] == 1883.8 + 900.0
    books = (await client.get("/api/v1/media/insights", params={"category": "audiobooks"})).json()
    assert books["totals"]["plays"] == 1 and books["top_works"][0]["id"] == str(alien)
