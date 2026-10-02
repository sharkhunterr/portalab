"""007 T029 — the live relay: types declaring ``live_permission`` reach the SSE outbox (permission-filtered,
private ones only for their subject user); others never do; relayed once despite redelivery."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from portalab.capabilities.events import EventType
from portalab.core.event_port import SubjectRef
from portalab.core.live import LiveEvent
from portalab.modules.events.consumers.live import live_consumer
from tests.events_fixtures import EventsHarness


async def test_live_relay(ev: EventsHarness) -> None:
    owner = uuid4()
    ev.types.register(
        EventType("ticket.updated", "t", visibility_class="restricted", live_permission="tickets.manage")
    )
    ev.types.register(
        EventType("reward.granted", "t", visibility_class="private", live_permission="users.self.manage")
    )
    ev.types.register(EventType("silent.thing", "t"))
    ev.consumers.register(live_consumer(ev.full.database, ev.types))
    async with ev.full.database.unit_of_work() as uow:
        for event_type, subject in (
            ("ticket.updated", SubjectRef("ticket", "t1")),
            ("reward.granted", SubjectRef("user", str(owner))),
            ("silent.thing", None),
        ):
            await ev.publisher.publish(
                uow.session,
                event_type,
                {"ref": "x"},
                occurred_at=datetime(2026, 10, 1, tzinfo=UTC),
                subject=subject,
            )
    await ev.module.dispatcher.run_once()
    await ev.module.dispatcher.run_once()
    async with ev.full.database.session() as session:
        rows = list((await session.execute(select(LiveEvent).order_by(LiveEvent.seq))).scalars())
    assert [(r.topic, r.permission, r.audience_user_id) for r in rows] == [
        ("ticket.updated", "tickets.manage", None),
        ("reward.granted", "users.self.manage", owner),
    ]
    assert "ref" not in rows[0].payload  # ids only: subscribers refetch through authorized APIs
