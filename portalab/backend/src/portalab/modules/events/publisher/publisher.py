"""The real ``EventPublisher`` (T011; R2, R3, R4, R7) — same signature as the kernel port used since spec 002.

In the producer's transaction: validate against the registry (else quarantine), derive the deduplication key
(duplicate ⇒ the original ``event_id``, no second row), then append to ``events.events`` with the envelope:
``event_id``, ``type``/``type_version``, ``occurred_at`` (real occurrence) distinct from ``received_at``
(receipt), ``source``, actor, subject, payload, provenance and correlation id.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.core.authz_port import Principal
from portalab.core.event_port import DEFAULT_SOURCE, PublishResult, SubjectRef
from portalab.core.ids import new_id
from portalab.core.logging import get_correlation_id
from portalab.core.time import Clock, require_aware, utc_now
from portalab.modules.events.dedup import service as dedup
from portalab.modules.events.dedup.keys import DedupKeyError, derive
from portalab.modules.events.models import Event
from portalab.modules.events.observability import metric_part, metrics
from portalab.modules.events.quarantine.service import store as quarantine
from portalab.modules.events.registry.types import validate


class EventStorePublisher:
    def __init__(
        self, registry: EventTypeRegistry = default_event_types, *, clock: Clock | None = None
    ) -> None:
        self.registry = registry
        self.clock = clock

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
        now = utc_now(self.clock)
        occurred = require_aware(occurred_at)
        payload = dict(metadata or {})
        checked = validate(self.registry, event_type, version, payload)
        raw = {
            "type": event_type,
            "version": version,
            "metadata": payload,
            "occurred_at": occurred.isoformat(),
            "source": source,
            "source_event_id": source_event_id,
            "dedup_key": dedup_key,
            "subject_type": subject.kind if subject else None,
            "subject_id": subject.id if subject else None,
        }
        if checked.payload is None:
            item = await quarantine(
                session,
                event_type=event_type,
                reason=checked.reason or "invalid_payload",
                detail=checked.detail,
                raw=raw,
                source=source,
                now=now,
            )
            return PublishResult(event_id=item, quarantined=True)
        registered = self.registry.get(event_type)
        assert registered is not None
        event_id = new_id()
        try:
            key = derive(
                registered,
                checked.payload,
                source=source,
                source_event_id=source_event_id,
                explicit=dedup_key,
            )
        except DedupKeyError as exc:
            item = await quarantine(
                session,
                event_type=event_type,
                reason="invalid_payload",
                detail=str(exc),
                raw=raw,
                source=source,
                now=now,
            )
            return PublishResult(event_id=item, quarantined=True)
        if key is not None:
            existing = await dedup.claim(session, event_type, key, event_id, now)
            if existing is not None:
                metrics.increment("events.ingestion.duplicate")
                return PublishResult(event_id=existing, duplicate=True)
        acting = actor.acting_for or actor.user_id if actor else None
        kind = (
            actor.channel
            if actor and (actor.user_id or actor.acting_for or actor.channel != "user")
            else "system"
        )
        await session.execute(
            insert(Event).values(
                event_id=event_id,
                retention_class=registered.retention_class,
                occurred_at=occurred,
                type=event_type,
                type_version=version,
                received_at=now,
                source_system=source,
                source_event_id=source_event_id,
                actor_user_id=acting,
                actor_kind=kind,
                subject_type=subject.kind if subject else None,
                subject_id=subject.id if subject else None,
                payload=checked.payload,
                provenance=dict(provenance or {}),
                correlation_id=get_correlation_id(),
                visibility_class=registered.visibility_class,
            )
        )
        metrics.increment("events.ingestion.accepted")
        metrics.increment(f"events.ingestion.type.{metric_part(event_type)}")
        return PublishResult(event_id=event_id)
