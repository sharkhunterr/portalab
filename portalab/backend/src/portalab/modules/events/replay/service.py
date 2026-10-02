"""Reconstruction (T028; R6, FR-027..030): feed a *replay-safe* projection the events of a window, in order
(``occurred_at``, then ``seq``), with ``replay=True`` and ``as_of=occurred_at``. Originals are never modified,
no side effect runs (``idempotent_effect`` answers False), and every run is recorded in ``replay_runs``."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.events import ConsumerRegistry, default_consumers
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.events.consumers.runtime import Context, envelope_of
from portalab.modules.events.models import Event, ReplayRun
from portalab.modules.events.observability import metrics

BATCH = 500


class ReplayService:
    def __init__(
        self,
        database: Database,
        publisher: EventPublisher,
        audit: AuditSink,
        *,
        consumers: ConsumerRegistry = default_consumers,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.publisher = publisher
        self.audit = audit
        self.consumers = consumers
        self.clock = clock

    async def rebuild(
        self,
        projection: str,
        *,
        actor: Principal,
        from_occurred_at: datetime | None = None,
        to_occurred_at: datetime | None = None,
    ) -> ReplayRun:
        consumer = self.consumers.get(projection)
        if consumer is None:
            raise NotFound("Unknown projection.", code="events.unknown_projection")
        if not consumer.replay_safe:
            raise ValidationFailed(
                "This consumer has side effects and cannot be replayed.", code="events.not_replay_safe"
            )
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            run = ReplayRun(
                projection=projection,
                from_occurred_at=from_occurred_at,
                to_occurred_at=to_occurred_at,
                requested_by=actor.user_id,
                status="running",
                processed=0,
                started_at=now,
            )
            uow.session.add(run)
            await uow.session.flush()
            started = await self.publisher.publish(
                uow.session,
                "events.replay_started",
                {"run": str(run.id), "projection": projection},
                occurred_at=now,
                actor=actor,
                source="events",
            )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="events.replay_started",
                    actor=actor,
                    resource=ResourceRef("projection", projection),
                    decision="allow",
                    context={"run": str(run.id)},
                    sensitive=True,
                    event_id=started.event_id,
                ),
            )
        processed, last_key = 0, None
        status = "finished"
        try:
            while True:
                statement = select(Event).order_by(Event.occurred_at, Event.seq).limit(BATCH)
                if "*" not in consumer.types:
                    statement = statement.where(Event.type.in_(sorted(consumer.types)))
                if from_occurred_at is not None:
                    statement = statement.where(Event.occurred_at >= from_occurred_at)
                if to_occurred_at is not None:
                    statement = statement.where(Event.occurred_at < to_occurred_at)
                if last_key is not None:
                    statement = statement.where(
                        (Event.occurred_at > last_key[0])
                        | ((Event.occurred_at == last_key[0]) & (Event.seq > last_key[1]))
                    )
                async with self.database.session() as session:
                    rows = list((await session.execute(statement)).scalars())
                if not rows:
                    break
                for row in rows:
                    context = Context(self.database, consumer.name, replay=True, as_of=row.occurred_at)
                    await consumer.handler(envelope_of(row), context)
                    processed += 1
                last_key = (rows[-1].occurred_at, rows[-1].seq)
        except Exception:
            status = "failed"
            raise
        finally:
            async with self.database.unit_of_work() as uow:
                current = await uow.session.get(ReplayRun, run.id, with_for_update=True)
                assert current is not None
                current.status, current.processed, current.finished_at = (
                    status,
                    processed,
                    utc_now(self.clock),
                )
                await self.publisher.publish(
                    uow.session,
                    "events.replay_finished",
                    {"run": str(run.id), "status": status, "processed": processed},
                    occurred_at=utc_now(self.clock),
                    actor=actor,
                    source="events",
                )
            metrics.increment(f"events.replay.{status}")
        return current

    async def get(self, run_id: UUID) -> ReplayRun | None:
        async with self.database.session() as session:
            return await session.get(ReplayRun, run_id)
