"""Consumer runtime (T015; R5, FR-005..011): independent cursors, delivery records, retry with backoff,
dead letters, and ``idempotent_effect`` for side effects under at-least-once delivery.

Each consumer advances on its own: a failing handler retries with exponential backoff while its cursor stays
on the failing event (per-consumer order is kept); after ``maxDeliveryAttempts`` the event becomes a dead
letter (visible to operators, ``events.consumer_dead_lettered``) and the consumer moves on. Other consumers
are never blocked, and producers never wait for consumers.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.events import Consumer, ConsumerRegistry, Envelope, EventTypeRegistry
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.logging import redact_text
from portalab.core.time import Clock, utc_now
from portalab.modules.events.models import ConsumerOffset, Delivery, EffectKey, Event
from portalab.modules.events.observability import log, metric_part, metrics
from portalab.modules.events.registry.upcasters import UpcasterRegistry, default_upcasters
from portalab.modules.events.settings import EventsConfig

HANDLER_TIMEOUT_SECONDS = 30.0


class Context:
    def __init__(self, database: Database, consumer: str, *, replay: bool, as_of: datetime) -> None:
        self.database = database
        self.consumer = consumer
        self.replay = replay
        self.as_of = as_of

    async def idempotent_effect(self, key: str) -> bool:
        if self.replay:
            return False  # reconstruction never re-runs side effects (R6)
        async with self.database.unit_of_work() as uow:
            inserted = (
                await uow.session.execute(
                    insert(EffectKey)
                    .values(consumer=self.consumer, effect_key=key[:256], created_at=utc_now())
                    .on_conflict_do_nothing(index_elements=["consumer", "effect_key"])
                    .returning(EffectKey.effect_key)
                )
            ).scalar_one_or_none()
        return inserted is not None


def envelope_of(row: Event, payload: dict[str, Any] | None = None) -> Envelope:
    return Envelope(
        event_id=row.event_id,
        seq=row.seq,
        type=row.type,
        type_version=row.type_version,
        occurred_at=row.occurred_at,
        received_at=row.received_at,
        source_system=row.source_system,
        source_event_id=row.source_event_id,
        actor_user_id=row.actor_user_id,
        actor_kind=row.actor_kind,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        payload=payload if payload is not None else dict(row.payload),
        provenance=dict(row.provenance),
        correlation_id=row.correlation_id,
    )


@dataclass(frozen=True, slots=True)
class ConsumerRun:
    consumer: str
    delivered: int
    failed: int
    dead: int


class Dispatcher:
    def __init__(
        self,
        database: Database,
        consumers: ConsumerRegistry,
        event_types: EventTypeRegistry,
        publisher: EventPublisher,
        *,
        upcasters: UpcasterRegistry = default_upcasters,
        config: EventsConfig | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.consumers = consumers
        self.event_types = event_types
        self.publisher = publisher
        self.upcasters = upcasters
        self.config = config or EventsConfig()
        self.clock = clock

    async def run_once(self) -> list[ConsumerRun]:
        runs = []
        for consumer in self.consumers.all():
            try:
                runs.append(await self.run_consumer(consumer))
            except Exception:
                log.exception("consumer dispatch failed", extra={"fields": {"consumer": consumer.name}})
        return runs

    async def _offset(self, name: str) -> int:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(ConsumerOffset)
                .values(consumer=name, last_seq=0, updated_at=utc_now(self.clock))
                .on_conflict_do_nothing(index_elements=["consumer"])
            )
            return int(
                await uow.session.scalar(
                    select(ConsumerOffset.last_seq).where(ConsumerOffset.consumer == name)
                )
            )

    async def run_consumer(self, consumer: Consumer) -> ConsumerRun:
        now = utc_now(self.clock)
        offset = await self._offset(consumer.name)
        statement = (
            select(Event).where(Event.seq > offset).order_by(Event.seq).limit(self.config.dispatch_batch_size)
        )
        if "*" not in consumer.types:
            statement = statement.where(Event.type.in_(sorted(consumer.types)))
        async with self.database.session() as session:
            rows = list((await session.execute(statement)).scalars())
            if rows:
                head = await session.get(Delivery, (consumer.name, rows[0].event_id))
                if (
                    head is not None
                    and head.status == "failed"
                    and head.next_attempt_at
                    and head.next_attempt_at > now
                ):
                    return ConsumerRun(consumer.name, 0, 0, 0)  # backing off on the head event
            newest = await session.scalar(select(Event.seq).order_by(Event.seq.desc()).limit(1))
        delivered = failed = dead = 0
        for row in rows:
            outcome = await self._deliver(consumer, row, now)
            if outcome == "failed":
                failed += 1
                break  # keep order: retry this event first
            delivered += outcome == "succeeded"
            dead += outcome == "dead"
        if newest is not None:
            last = await self._current_offset(consumer.name)
            metrics.gauge(f"events.consumer.lag.{metric_part(consumer.name)}", max(0, newest - last))
        return ConsumerRun(consumer.name, delivered, failed, dead)

    async def _current_offset(self, name: str) -> int:
        async with self.database.session() as session:
            return int(
                await session.scalar(select(ConsumerOffset.last_seq).where(ConsumerOffset.consumer == name))
                or 0
            )

    def _payload_for(self, consumer: Consumer, row: Event) -> dict[str, Any]:
        registered = self.event_types.get(row.type)
        target = consumer.supported_versions.get(
            row.type, registered.version if registered else row.type_version
        )
        if row.type_version > target:
            raise LookupError(
                f"{row.type} v{row.type_version} is newer than what {consumer.name} understands"
            )
        return self.upcasters.upcast(row.type, dict(row.payload), row.type_version, target)

    async def _deliver(self, consumer: Consumer, row: Event, now: datetime) -> str:
        error: str | None = None
        try:
            payload = self._payload_for(consumer, row)
            context = Context(self.database, consumer.name, replay=False, as_of=row.occurred_at)
            await asyncio.wait_for(
                consumer.handler(envelope_of(row, payload), context), HANDLER_TIMEOUT_SECONDS
            )
            status = "succeeded"
        except Exception as exc:
            error = redact_text(f"{type(exc).__name__}: {exc}")[:512]
            status = "failed"
        async with self.database.unit_of_work() as uow:
            delivery = await uow.session.get(Delivery, (consumer.name, row.event_id), with_for_update=True)
            if delivery is None:
                delivery = Delivery(
                    consumer=consumer.name,
                    event_id=row.event_id,
                    event_seq=row.seq,
                    status="pending",
                    attempts=0,
                    updated_at=now,
                )
                uow.session.add(delivery)
            delivery.attempts += 1
            delivery.updated_at = now
            delivery.last_error = error
            if status == "failed" and delivery.attempts >= self.config.max_delivery_attempts:
                status = "dead"
            delivery.status = status
            if status == "failed":
                delay = self.config.retry_backoff_seconds * 2 ** (delivery.attempts - 1)
                delivery.next_attempt_at = now + timedelta(seconds=min(delay, 3600))
            else:
                delivery.next_attempt_at = None
                offset = await uow.session.get(ConsumerOffset, consumer.name, with_for_update=True)
                assert offset is not None
                offset.last_seq = max(offset.last_seq, row.seq)
                offset.updated_at = now
            if status == "dead":
                await self.publisher.publish(
                    uow.session,
                    "events.consumer_dead_lettered",
                    {"consumer": consumer.name, "event_type": row.type, "event_ref": str(row.event_id)},
                    occurred_at=now,
                    subject=SubjectRef("event", str(row.event_id)),
                    source="events",
                    dedup_key=f"dead:{consumer.name}:{row.event_id}",
                )
        metrics.increment(f"events.deliveries.{status}")
        if status != "succeeded":
            log.warning(
                "delivery " + status, extra={"fields": {"consumer": consumer.name, "event_type": row.type}}
            )
        return status
