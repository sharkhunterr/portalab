"""002 T004 — kernel EventPublisher outbox: envelope fields, atomicity with the caller, dedup, no secrets."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.event_port import OutboxEvent, OutboxEventPublisher, SubjectRef
from portalab.core.time import FixedClock

OCCURRED = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
RECEIVED = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


async def test_envelope_and_dedup(database: Database) -> None:
    publisher = OutboxEventPublisher(FixedClock(RECEIVED))
    actor = Principal(user_id=uuid4())
    subject = SubjectRef("user", str(actor.user_id))
    async with database.unit_of_work() as uow:
        first = await publisher.publish(
            uow.session,
            "user.created",
            {"state": "active"},
            occurred_at=OCCURRED,
            actor=actor,
            subject=subject,
            dedup_key="user:x:created",
        )
        again = await publisher.publish(
            uow.session,
            "user.created",
            {"state": "active"},
            occurred_at=OCCURRED,
            actor=actor,
            subject=subject,
            dedup_key="user:x:created",
        )
    assert not first.duplicate and again.duplicate and again.event_id == first.event_id
    async with database.session() as session:
        row = (await session.execute(select(OutboxEvent))).scalar_one()
    assert (row.type, row.version, row.source) == ("user.created", 1, "portalab")
    assert (row.occurred_at, row.received_at) == (OCCURRED, RECEIVED)
    assert (row.actor_id, row.actor_channel) == (actor.user_id, "user")
    assert (row.subject_kind, row.subject_id) == ("user", str(actor.user_id))
    assert row.event_metadata == {"state": "active"}


async def test_rolled_back_transaction_publishes_nothing(database: Database) -> None:
    publisher = OutboxEventPublisher()
    with pytest.raises(RuntimeError):
        async with database.unit_of_work() as uow:
            await publisher.publish(uow.session, "user.created", occurred_at=OCCURRED)
            raise RuntimeError("state change failed")
    async with database.session() as session:
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 0


@pytest.mark.parametrize(
    ("event_type", "metadata"),
    [("nodot", {}), ("user.created", {"password": "x"}), ("user.created", {"nested": {"api_token": "y"}})],
)
async def test_invalid_events_are_refused(
    database: Database, event_type: str, metadata: dict[str, object]
) -> None:
    async with database.unit_of_work() as uow:
        with pytest.raises(ValueError):
            await OutboxEventPublisher().publish(uow.session, event_type, metadata, occurred_at=OCCURRED)
