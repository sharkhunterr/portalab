"""027 — editing the dates of a running campaign applies to the running period at once: an earlier end
shows (and ends it) on that date, not on the old one; an end moved before now ends it now."""

import pytest
from sqlalchemy import select

from portalab.modules.campaigns.models import Occurrence
from tests.integration.campaigns.conftest import HALLOWEEN, CampHarness, later, paris

pytestmark = pytest.mark.integration


async def _running(cm: CampHarness) -> Occurrence:
    async with cm.database.session() as session:
        return (await session.execute(select(Occurrence).where(Occurrence.status == "active"))).scalar_one()


async def test_a_moved_end_applies_to_the_running_period(cm: CampHarness) -> None:
    campaign = await cm.create()
    await cm.at(later(paris(10, 20, 0), minutes=1))
    assert (await _running(cm)).end_at == paris(11, 1, 0)
    shorter = {**HALLOWEEN, "schedule": {**HALLOWEEN["schedule"], "end_at": "2026-10-25T00:00:00"}}
    await cm.campaigns.definitions.publish(cm.p("boss"), campaign, shorter)
    running = await _running(cm)
    assert running.end_at == paris(10, 25, 0) and running.version == 2
    assert running.start_at == paris(10, 20, 0)  # its start is kept

    cm.clock.set(paris(10, 23, 12))
    over = {**HALLOWEEN, "schedule": {**HALLOWEEN["schedule"], "end_at": "2026-10-22T00:00:00"}}
    await cm.campaigns.definitions.publish(cm.p("boss"), campaign, over)
    await cm.at(later(paris(10, 23, 12), minutes=1))
    async with cm.database.session() as session:
        statuses = (await session.execute(select(Occurrence.status))).scalars().all()
    assert "active" not in statuses  # ended now, not on the old date
