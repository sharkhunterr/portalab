"""Quarantine (T012; FR-014): unknown types, unsupported versions, invalid payloads and personal-looking
fields are kept aside (redacted) instead of entering history; an operator can release (re-publish after the
type was fixed) or discard them — both sensitive, audited actions."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound
from portalab.core.logging import redact
from portalab.core.time import Clock, utc_now
from portalab.modules.events.models import Quarantine
from portalab.modules.events.observability import metrics


async def store(
    session: AsyncSession,
    *,
    event_type: str,
    reason: str,
    detail: str,
    raw: dict[str, Any],
    source: str,
    now: datetime,
) -> UUID:
    row = Quarantine(
        received_at=now,
        event_type=event_type[:128],
        reason=reason,
        detail=detail[:2000],
        raw=redact(raw),
        source_system=source[:128],
        status="open",
    )
    session.add(row)
    await session.flush()
    metrics.increment(f"events.ingestion.quarantined.{reason}")
    return row.id


class QuarantineService:
    def __init__(self, database: Database, audit: AuditSink, *, clock: Clock | None = None) -> None:
        self.database = database
        self.audit = audit
        self.clock = clock

    async def list(self, status: str | None, limit: int = 100) -> list[Quarantine]:
        statement = select(Quarantine).order_by(Quarantine.received_at.desc()).limit(limit)
        if status:
            statement = statement.where(Quarantine.status == status)
        async with self.database.session() as session:
            return list((await session.execute(statement)).scalars())

    async def resolve(
        self, actor: Principal, item_id: UUID, action: str, publisher: Any = None
    ) -> Quarantine:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Quarantine, item_id, with_for_update=True)
            if row is None:
                raise NotFound("Unknown quarantined event.", code="events.quarantine_not_found")
            if row.status != "open":
                raise Conflict("This item was already handled.", code="events.quarantine_closed")
            result = None
            if action == "release":
                raw = dict(row.raw)
                result = await publisher.publish(
                    uow.session,
                    str(raw.get("type", row.event_type)),
                    dict(raw.get("metadata") or {}),
                    occurred_at=datetime.fromisoformat(str(raw["occurred_at"])),
                    source=str(raw.get("source", row.source_system)),
                    version=int(raw.get("version", 1)),
                    source_event_id=raw.get("source_event_id"),
                    dedup_key=raw.get("dedup_key"),
                )
                if result.quarantined:
                    raise Conflict(
                        "The event is still invalid; fix its type first.", code="events.still_invalid"
                    )
            row.status = "released" if action == "release" else "discarded"
            row.resolved_by = actor.user_id
            row.resolved_at = utc_now(self.clock)
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action=f"events.quarantine_{row.status}",
                    actor=actor,
                    resource=ResourceRef("quarantined_event", str(row.id)),
                    decision="allow",
                    result="success",
                    context={"event_type": row.event_type, "reason": row.reason},
                    sensitive=True,
                    event_id=result.event_id if result is not None else None,
                ),
            )
            return row
