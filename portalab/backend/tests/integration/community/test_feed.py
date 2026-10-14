"""012 T009 — activity feed: allow-listed events project once (redelivery idempotent on
``source_event_id``); private event types and Private actors never enter; a visibility change takes effect at
read time; entries reference their source and carry a localization key (no like/reaction/comment fields);
retention purge; erased with the actor; an anonymous actor (issue 120) shows without name or profile."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from portalab.modules.community.models import FeedEntry
from portalab.modules.events.consumers.runtime import envelope_of
from portalab.modules.events.models import Event
from tests.integration.community.conftest import CoHarness
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def count(co: CoHarness) -> int:
    async with co.database.session() as session:
        return int(await session.scalar(select(func.count()).select_from(FeedEntry)) or 0)


async def test_projection_and_read_time_visibility(co: CoHarness, client: AsyncClient) -> None:
    await co.emit("achievement.unlocked", "ursula", {"achievement": "first-steps"})
    await co.emit("user.level_up", "ursula", {"level": 2})
    await co.emit("test.secret", "ursula", {"value": 1})  # allow-listed, but a private event type
    await co.emit("economy.coins_spent", "ursula", {"amount": 3, "source": "marketplace"})  # not listed
    await co.prefer("vera", "community_activity", "private")
    await co.emit("achievement.unlocked", "vera", {"achievement": "first-steps"})  # never enters
    assert await count(co) == 2

    await login(client, "ulrich")
    body = (await client.get("/api/v1/community/feed")).json()
    assert [i["kind"] for i in body["items"]] == ["user.level_up", "achievement.unlocked"]
    entry = body["items"][1]
    assert entry["text_key"] == "community:feed.achievement.unlocked"
    assert entry["params"] == {"achievement": "first-steps"} and entry["actor_name"] == "Ursula"
    assert entry["source_event_id"] and entry["subject_ref"] is None
    assert not {"likes", "reactions", "comments"} & set(entry)

    async with co.database.session() as session:  # a redelivery projects nothing new
        source = await session.scalar(select(FeedEntry.source_event_id).limit(1))
        stored = await session.scalar(select(Event).where(Event.event_id == source))
    assert stored is not None
    assert await co.module.projector.project(envelope_of(stored, dict(stored.payload))) is False
    assert await count(co) == 2

    # issue 120: an anonymous actor stays in the feed — no name, and no id leading to the profile
    await co.prefer("ursula", "progression", "private")
    hidden = (await client.get("/api/v1/community/feed")).json()["items"]
    assert [(i["actor_name"], i["anonymous"]) for i in hidden] == [(None, True), (None, True)]
    assert str(co.people["ursula"]) not in {i["actor_id"] for i in hidden}
    assert len({i["actor_id"] for i in hidden}) == 2  # not one stand-in that would tie entries together
    await co.prefer("ursula", "progression", "community")

    await co.prefer("ursula", "community_activity", "private")
    assert (await client.get("/api/v1/community/feed")).json()["items"] == []
    await login(client, "ursula")  # the actor still sees their own entries
    assert len((await client.get("/api/v1/community/feed")).json()["items"]) == 2
    await co.prefer("ursula", "progression", "private")  # and their own name, anonymous or not
    mine = (await client.get("/api/v1/community/feed")).json()["items"]
    assert {(i["actor_name"], i["anonymous"]) for i in mine} == {("Ursula", False)}


async def test_pagination_retention_and_erasure(co: CoHarness, client: AsyncClient) -> None:
    for level in range(2, 7):
        await co.emit("user.level_up", "ursula", {"level": level})
        co.clock.advance(timedelta(minutes=1))
    await login(client, "ulrich")
    first = (await client.get("/api/v1/community/feed", params={"limit": 3})).json()
    assert [i["params"]["level"] for i in first["items"]] == [6, 5, 4] and first["next_cursor"]
    rest = (
        await client.get("/api/v1/community/feed", params={"limit": 3, "cursor": first["next_cursor"]})
    ).json()
    assert [i["params"]["level"] for i in rest["items"]] == [3, 2]

    co.clock.advance(timedelta(days=co.module.config.feed_retention_days + 1))
    await co.emit("user.level_up", "ulrich", {"level": 2})
    assert await co.module.feed.purge(co.module.config.feed_retention_days) == 5
    assert await count(co) == 1

    from portalab.modules.community.privacy.participant import CommunityParticipant

    participant = CommunityParticipant(co.database)
    exported = await participant.export(co.people["ulrich"])
    assert [r.category for r in exported] == ["community.feed_entry"]
    await participant.erase(co.people["ulrich"], "final")
    await participant.erase(co.people["ulrich"], "final")  # idempotent
    assert await count(co) == 0
