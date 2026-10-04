"""007 T013/T014 — fan-out: independent consumers; a failing one retries then dead-letters while others
advance; producers never wait; a new consumer needs no producer change; redelivery after a crash applies
``idempotent_effect`` once and offsets resume."""

from datetime import UTC, datetime

from sqlalchemy import select

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope, EventType
from portalab.modules.events.models import ConsumerOffset, Delivery, Event
from tests.events_fixtures import EventsHarness

OCCURRED = datetime(2026, 10, 1, 10, tzinfo=UTC)


async def _publish(ev: EventsHarness, count: int) -> None:
    async with ev.full.database.unit_of_work() as uow:
        for index in range(count):
            await ev.publisher.publish(uow.session, "demo.happened", {"n": index}, occurred_at=OCCURRED)


async def test_isolation_and_dead_letter(ev: EventsHarness) -> None:
    ev.types.register(EventType("demo.happened", "t"))
    seen: list[int] = []

    async def good(event: Envelope, ctx: ConsumerContext) -> None:
        seen.append(int(event.payload["n"]))

    async def bad(event: Envelope, ctx: ConsumerContext) -> None:
        raise ValueError("token=abcdef123456 broke")

    ev.consumers.register(Consumer("good", frozenset({"demo.happened"}), good, "t"))
    ev.consumers.register(Consumer("bad", frozenset({"demo.happened"}), bad, "t"))
    await _publish(ev, 3)
    for _ in range(12):
        await ev.module.dispatcher.run_once()
    assert seen == [0, 1, 2]
    async with ev.full.database.session() as session:
        deliveries = {(d.consumer, d.status) for d in (await session.execute(select(Delivery))).scalars()}
        offsets = dict(
            (await session.execute(select(ConsumerOffset.consumer, ConsumerOffset.last_seq))).all()
        )
        last = await session.scalar(
            select(Event.seq).where(Event.type == "demo.happened").order_by(Event.seq.desc())
        )
        errors = (
            (await session.execute(select(Delivery.last_error).where(Delivery.consumer == "bad")))
            .scalars()
            .all()
        )
        dead_events = (
            (await session.execute(select(Event.type).where(Event.type == "events.consumer_dead_lettered")))
            .scalars()
            .all()
        )
    assert ("bad", "dead") in deliveries and ("good", "succeeded") in deliveries
    assert offsets["good"] >= last and offsets["bad"] >= last  # the dead letters did not block forever
    assert all("abcdef123456" not in (error or "") for error in errors)
    assert len(dead_events) == 3

    # a new consumer starts from the beginning without any producer change
    late: list[int] = []

    async def newcomer(event: Envelope, ctx: ConsumerContext) -> None:
        late.append(int(event.payload["n"]))

    ev.consumers.register(Consumer("late", frozenset({"demo.happened"}), newcomer, "t"))
    await ev.module.dispatcher.run_once()
    assert late == [0, 1, 2]


async def test_idempotent_effect_on_redelivery(ev: EventsHarness) -> None:
    ev.types.register(EventType("demo.happened", "t"))
    effects: list[str] = []
    crash = {"once": True}

    async def rewarding(event: Envelope, ctx: ConsumerContext) -> None:
        if await ctx.idempotent_effect(f"reward:{event.event_id}"):
            effects.append(str(event.event_id))
        if crash["once"]:
            crash["once"] = False
            raise ConnectionError("crashed after the effect, before acknowledging")

    ev.consumers.register(Consumer("rewards", frozenset({"demo.happened"}), rewarding, "t"))
    await _publish(ev, 1)
    await ev.module.dispatcher.run_once()  # crash: delivery failed, offset not advanced
    await ev.module.dispatcher.run_once()  # redelivery: effect key already present
    assert len(effects) == 1
    async with ev.full.database.session() as session:
        delivery = (await session.execute(select(Delivery))).scalar_one()
    assert delivery.status == "succeeded" and delivery.attempts == 2


async def test_filtered_consumer_follows_the_head(ev: EventsHarness) -> None:
    """027 T094: a consumer whose types never occur is not reported thousands of events behind."""
    ev.types.register(EventType("demo.happened", "t"))

    async def never(event: Envelope, ctx: ConsumerContext) -> None:
        raise AssertionError("no matching event was published")

    ev.consumers.register(Consumer("quiet", frozenset({"demo.other"}), never, "t"))
    await _publish(ev, 3)
    await ev.module.dispatcher.run_once()
    snapshot = await ev.module.stats.snapshot()
    assert snapshot.lag_by_consumer["quiet"] == 0
