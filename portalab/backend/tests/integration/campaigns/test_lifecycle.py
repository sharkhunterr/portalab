"""014 T009 — boundaries (fixed clock): ``campaign.started`` / ``ending_soon`` / ``ended`` emitted once; the
interval opens at the scheduled instant and closes at the scheduled end, atomically with the events; after
scheduler downtime the reconciler repairs and logs the actual time; repeated runs are idempotent; the
next yearly occurrence keeps the campaign scheduled."""

import pytest
from sqlalchemy import select, text

from portalab.modules.campaigns.models import Campaign, Occurrence
from portalab.modules.campaigns.observability import metrics
from tests.integration.campaigns.conftest import HALLOWEEN, CampHarness, later, paris

pytestmark = pytest.mark.integration


async def events(cm: CampHarness) -> list[str]:
    async with cm.database.session() as session:
        return list(
            (
                await session.execute(
                    text("SELECT type FROM events.events WHERE type LIKE 'campaign.%' ORDER BY seq")
                )
            ).scalars()
        )


async def state(cm: CampHarness, campaign: object) -> str:
    async with cm.database.session() as session:
        row = await session.get(Campaign, campaign)
        assert row is not None
        return row.state


async def test_schedule_boundaries(cm: CampHarness) -> None:
    campaign = await cm.create()
    assert await state(cm, campaign) == "scheduled"
    async with cm.database.session() as session:
        windows = (
            (await session.execute(select(Occurrence.start_at).order_by(Occurrence.index))).scalars().all()
        )
    assert [w.year for w in windows] == [2026, 2027]
    start = paris(10, 20, 0)
    for moment in (later(start, seconds=30), later(start, minutes=1)):
        await cm.at(moment)
    assert await state(cm, campaign) == "active"
    async with cm.database.session() as session:
        opened = await session.scalar(text("SELECT opened_at FROM campaigns.open_intervals"))
    assert opened == start  # logged at the scheduled instant (within tolerance)
    await cm.at(paris(10, 30, 12))
    await cm.at(paris(10, 31, 6))
    await cm.at(paris(10, 31, 7))
    await cm.at(later(paris(11, 1, 0), minutes=1))
    async with cm.database.session() as session:
        during = (
            await session.execute(text("SELECT lower(during), upper(during) FROM campaigns.activation_log"))
        ).one()
        open_rows = await session.scalar(text("SELECT count(*) FROM campaigns.open_intervals"))
    assert (during[0], during[1]) == (start, paris(11, 1, 0)) and open_rows == 0
    assert await events(cm) == [
        "campaign.created",
        "campaign.started",
        "campaign.ending_soon",
        "campaign.ended",
    ]
    assert await state(cm, campaign) == "scheduled"  # next year's occurrence
    await cm.at(later(paris(11, 1, 0), minutes=2))
    assert len(await events(cm)) == 4


async def test_downtime_is_repaired_with_actual_times(cm: CampHarness) -> None:
    before = metrics.snapshot().get("campaigns.boundary_late", 0)
    definition = {**HALLOWEEN, "schedule": {**HALLOWEEN["schedule"], "recurrence": {"kind": "none"}}}
    await cm.create("late", definition)
    repaired = paris(10, 20, 3)
    await cm.at(repaired)
    async with cm.database.session() as session:
        opened = await session.scalar(text("SELECT opened_at FROM campaigns.open_intervals"))
    assert opened == repaired and metrics.snapshot()["campaigns.boundary_late"] == before + 1
    await cm.at(paris(11, 3, 9))  # down over the end: the interval still closes at the scheduled end
    async with cm.database.session() as session:
        closed = await session.scalar(text("SELECT upper(during) FROM campaigns.activation_log"))
        final = await session.scalar(text("SELECT state FROM campaigns.campaigns"))
    assert closed == paris(11, 1, 0) and final == "ended"
