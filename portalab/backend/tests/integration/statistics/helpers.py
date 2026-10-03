"""Helpers for statistics integration tests."""

from sqlalchemy import select

from portalab.capabilities.events import Envelope
from portalab.modules.events.consumers.runtime import envelope_of
from portalab.modules.events.models import Event
from tests.integration.statistics.conftest import StatsHarness


async def first_envelope(stats: StatsHarness, event_type: str) -> Envelope:
    async with stats.database.session() as session:
        row = (
            await session.execute(select(Event).where(Event.type == event_type).order_by(Event.seq).limit(1))
        ).scalar_one()
    return envelope_of(row)
