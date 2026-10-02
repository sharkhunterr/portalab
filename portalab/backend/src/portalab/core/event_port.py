"""Domain-event publishing port + transactional outbox adapter (spec 002 research R14, EVENT_MODEL.md).

Producers publish **inside their own transaction** so the event commits atomically with the state change.
The envelope mirrors ``architecture/EVENT_MODEL.md``: ``event_id``, ``type``, ``occurred_at`` (real
occurrence), ``received_at`` (portal receipt), ``source``, ``actor``, ``object`` (subject reference),
``metadata`` and ``version``. Duplicate publications carrying the same ``dedup_key`` are no-ops (CD-012).

The Events module (spec 007) provides the real implementation of :class:`EventPublisher` (type registry,
history store, consumers) and drains this outbox; until then :class:`OutboxEventPublisher` is the adapter.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import BigInteger, Identity, Integer, String, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from portalab.core.authz_port import Principal
from portalab.core.db import CoreBase, TZDateTime
from portalab.core.ids import new_id
from portalab.core.jobs.queue import check_payload
from portalab.core.logging import get_correlation_id
from portalab.core.privacy_registry import pii
from portalab.core.time import Clock, require_aware, utc_now

DEFAULT_SOURCE = "portalab"


@dataclass(frozen=True, slots=True)
class SubjectRef:
    """The object an event is about (``kind`` + id), e.g. ``SubjectRef("user", str(user_id))``."""

    kind: str
    id: str


@dataclass(frozen=True, slots=True)
class PublishResult:
    event_id: UUID
    duplicate: bool = False
    quarantined: bool = False  # invalid or unknown type: kept aside for review, not in history (spec 007)


class EventPublisher(Protocol):
    async def publish(
        self,
        session: AsyncSession,
        event_type: str,
        metadata: Mapping[str, Any] | None = None,
        *,
        occurred_at: datetime,
        actor: Principal | None = None,
        subject: SubjectRef | None = None,
        source: str = DEFAULT_SOURCE,
        dedup_key: str | None = None,
        version: int = 1,
        source_event_id: str | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> PublishResult: ...


class OutboxEvent(CoreBase):
    """Envelope rows waiting to be taken over by the Events module (spec 007)."""

    __tablename__ = "event_outbox"

    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(info=pii("identifier"))
    actor_channel: Mapped[str | None] = mapped_column(String(16))
    subject_kind: Mapped[str | None] = mapped_column(String(64))
    subject_id: Mapped[str | None] = mapped_column(String(128))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    dedup_key: Mapped[str | None] = mapped_column(String(256), unique=True)


class OutboxEventPublisher:
    """Baseline :class:`EventPublisher`: one ``core.event_outbox`` row per event, in the caller's session."""

    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock

    async def publish(
        self,
        session: AsyncSession,
        event_type: str,
        metadata: Mapping[str, Any] | None = None,
        *,
        occurred_at: datetime,
        actor: Principal | None = None,
        subject: SubjectRef | None = None,
        source: str = DEFAULT_SOURCE,
        dedup_key: str | None = None,
        version: int = 1,
        source_event_id: str | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> PublishResult:
        if not event_type or "." not in event_type:
            raise ValueError(f"event type {event_type!r} must look like '<domain>.<action>'")
        if version < 1:
            raise ValueError("event version must be >= 1")
        payload = dict(metadata or {})
        check_payload(payload)  # events reference ids, never carry secrets
        event_id = new_id()
        values: dict[str, Any] = {
            "event_id": event_id,
            "type": event_type,
            "version": version,
            "occurred_at": require_aware(occurred_at),
            "received_at": utc_now(self._clock),
            "source": source,
            "actor_id": (actor.acting_for or actor.user_id) if actor else None,
            "actor_channel": actor.channel if actor else None,
            "subject_kind": subject.kind if subject else None,
            "subject_id": subject.id if subject else None,
            "event_metadata": payload,  # ORM attribute of the "metadata" column
            "correlation_id": get_correlation_id(),
            "dedup_key": dedup_key,
        }
        statement = insert(OutboxEvent).values(**values)
        if dedup_key is not None:
            statement = statement.on_conflict_do_nothing(index_elements=["dedup_key"])
        inserted = (await session.execute(statement.returning(OutboxEvent.event_id))).scalar_one_or_none()
        if inserted is not None:
            return PublishResult(event_id=inserted)
        existing = await session.execute(
            select(OutboxEvent.event_id).where(OutboxEvent.dedup_key == dedup_key)
        )
        return PublishResult(event_id=existing.scalar_one(), duplicate=True)
