"""017 T005/T008 — schema; buckets equal an oracle computed over the seeded events; a redelivered event never
counts twice; an out-of-order event lands in its own ``occurred_at`` day (statistics time zone); replaying
the history through 007's ``ReplayService`` reproduces identical buckets; activating a statistic computes
its history; forward-only versions keep the history of the earlier version."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text

from portalab.core.authz_port import Principal
from portalab.modules.events.replay.service import ReplayService
from portalab.modules.statistics.models import AppliedEvent, Bucket, Member
from portalab.modules.statistics.projection.consumers import consumer_name
from tests.integration.privacy.conftest import NOW
from tests.integration.statistics.conftest import StatsHarness

pytestmark = pytest.mark.integration

MINUTES = {
    "key": "media.minutes",
    "title_key": "t",
    "domain": "media",
    "scope": "community",
    "event_types": ["media.played"],
    "measure": {"kind": "sum", "field": "minutes"},
    "dimensions": ["genre"],
}


async def buckets(stats: StatsHarness, key: str) -> list[tuple[object, ...]]:
    async with stats.database.session() as session:
        rows = await session.execute(
            select(
                Bucket.def_version,
                Bucket.bucket_day,
                Bucket.dims,
                Bucket.count,
                Bucket.sum,
                Bucket.min,
                Bucket.max,
            )
            .where(Bucket.stat_key == key)
            .order_by(Bucket.bucket_day, Bucket.dims_hash)
        )
        return [(*r[:4], int(r[4]), int(r[5]), int(r[6])) for r in rows]


async def test_schema(stats: StatsHarness) -> None:
    await stats.define(MINUTES)
    async with stats.database.session() as session:
        tables = set(
            (
                await session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'stats'"))
            ).scalars()
        )
        with pytest.raises(Exception, match="append-only"):
            await session.execute(text("UPDATE stats.definitions SET domain = 'x'"))
    assert {
        "definitions",
        "definition_status",
        "buckets",
        "members",
        "applied_events",
        "unlocks",
        "wrapped_snapshots",
    } <= tables


async def test_projection_matches_oracle_and_replays(stats: StatsHarness) -> None:
    users = [uuid4() for _ in range(3)]
    plays = [  # (hours before NOW, user index, minutes, genre)
        (1, 0, 30, "rock"),
        (2, 1, 45, "rock"),
        (25, 2, 10, "jazz"),
        (49, 0, 20, "rock"),
        (26, 1, 5, "jazz"),  # published later than the 49 h one: out of order
    ]
    for hours, who, minutes, genre in plays:
        await stats.publish(
            "media.played",
            {"minutes": minutes, "genre": genre, "service_id": "s1"},
            at=NOW - timedelta(hours=hours),
            actor=users[who],
        )
    version = await stats.define(MINUTES)  # activation computes the history
    await stats.dispatch()
    oracle: dict[tuple[object, str], list[int]] = {}
    for hours, _, minutes, genre in plays:
        day = (NOW - timedelta(hours=hours)).date()  # statistics zone defaults to UTC
        oracle.setdefault((day, genre), []).append(minutes)
    expected = [
        (version, day, {"genre": genre}, len(values), sum(values), min(values), max(values))
        for (day, genre), values in sorted(oracle.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    ]
    got = await buckets(stats, "media.minutes")
    assert sorted(map(str, got)) == sorted(map(str, expected))

    # redelivery of an already-folded event: no double count
    from tests.integration.statistics.helpers import first_envelope

    definition = (await stats.module.definitions.get_active("media.minutes")).definition  # type: ignore[union-attr]
    envelope = await first_envelope(stats, "media.played")
    assert await stats.module.projection.apply(definition, version, envelope) is False
    assert await buckets(stats, "media.minutes") == got

    # replay (007) after wiping the projection reproduces identical buckets
    async with stats.database.unit_of_work() as uow:
        for model in (Bucket, Member, AppliedEvent):
            await uow.session.execute(delete(model).where(model.stat_key == "media.minutes"))
    replay = ReplayService(
        stats.database, stats.ev.publisher, stats.ev.full.authz.audit, consumers=stats.ev.consumers
    )
    await replay.rebuild(consumer_name("media.minutes", version), actor=Principal(channel="system"))
    assert await buckets(stats, "media.minutes") == got


async def test_forward_only_keeps_history(stats: StatsHarness) -> None:
    actor = uuid4()
    await stats.publish(
        "media.played",
        {"minutes": 10, "genre": "rock", "service_id": "s1"},
        at=NOW - timedelta(days=2),
        actor=actor,
    )
    v1 = await stats.define({**MINUTES, "dimensions": []})
    await stats.dispatch()
    v2 = await stats.module.definitions.save(
        None, {**MINUTES, "dimensions": [], "filter": [{"field": "genre", "op": "eq", "value": "jazz"}]}
    )
    await stats.module.activate(Principal(channel="system"), "media.minutes", v2)
    await stats.publish(
        "media.played",
        {"minutes": 7, "genre": "rock", "service_id": "s1"},
        at=NOW - timedelta(hours=1),
        actor=actor,
    )
    await stats.publish(
        "media.played",
        {"minutes": 3, "genre": "jazz", "service_id": "s1"},
        at=NOW - timedelta(hours=1),
        actor=actor,
    )
    await stats.dispatch()
    rows = await buckets(stats, "media.minutes")
    assert [(r[0], int(r[4])) for r in rows] == [(v1, 10), (v2, 3)]  # history under v1, new rule from v2
    active = await stats.module.definitions.get_active("media.minutes")
    assert active is not None and active.lineage == (v1, v2)
