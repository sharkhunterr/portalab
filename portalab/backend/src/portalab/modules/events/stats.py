"""``events.stats`` provider: consumer lag, dead letters and quarantine for Observability (025)."""

from sqlalchemy import func, select

from portalab.capabilities.events import ConsumerRegistry, EventStatsSnapshot
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.events.models import ConsumerOffset, Delivery, Event, Quarantine


class EventStatsProvider:
    def __init__(
        self, database: Database, consumers: ConsumerRegistry, *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.consumers = consumers
        self.clock = clock

    async def snapshot(self) -> EventStatsSnapshot:
        async with self.database.session() as session:
            head = int(await session.scalar(select(func.coalesce(func.max(Event.seq), 0))) or 0)
            offsets = {
                consumer: int(seq)
                for consumer, seq in (
                    await session.execute(select(ConsumerOffset.consumer, ConsumerOffset.last_seq))
                ).all()
            }
            dead = int(
                await session.scalar(
                    select(func.count()).select_from(Delivery).where(Delivery.status == "dead")
                )
                or 0
            )
            failed = int(
                await session.scalar(
                    select(func.count()).select_from(Delivery).where(Delivery.status == "failed")
                )
                or 0
            )
            oldest = await session.scalar(
                select(func.min(Delivery.updated_at)).where(Delivery.status == "failed")
            )
            quarantined = int(
                await session.scalar(
                    select(func.count()).select_from(Quarantine).where(Quarantine.status == "open")
                )
                or 0
            )
        lag = {
            consumer.name: max(head - offsets.get(consumer.name, 0), 0) for consumer in self.consumers.all()
        }
        age = (utc_now(self.clock) - oldest).total_seconds() if oldest else None
        return EventStatsSnapshot(head, lag, dead, failed, quarantined, age)
