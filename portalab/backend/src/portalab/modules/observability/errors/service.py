"""Error management (T010): list with filters, acknowledge, resolve with a resolution note (audited)."""

from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.observability.errors.recorder import ErrorRecorder
from portalab.modules.observability.models import ErrorRecord


def error_out(row: ErrorRecord, *, full_context: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(row.id),
        "component": row.component,
        "category": row.category,
        "type": row.error_type,
        "level": row.level,
        "count": row.count,
        "first_seen_at": row.first_seen_at.isoformat(),
        "last_seen_at": row.last_seen_at.isoformat(),
        "state": row.state,
        "service_ref": row.service_ref,
        "plugin_ref": row.plugin_ref,
        "event_ref": row.event_ref,
        "resolution": row.resolution,
    }
    if full_context:
        out |= {
            "message": row.message,
            "context": row.context,
            "user_ref": str(row.user_ref) if row.user_ref else None,
        }
    else:  # Support level: diagnosable shape without context values or user references
        out |= {"message": row.message, "context_keys": sorted(row.context)}
    return out


class ErrorService:
    def __init__(
        self, database: Database, recorder: ErrorRecorder, audit: AuditSink, *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.recorder = recorder
        self.audit = audit
        self.clock = clock

    async def errors(
        self, *, state: str | None = None, component: str | None = None, full_context: bool, limit: int = 100
    ) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            statement = select(ErrorRecord).order_by(ErrorRecord.last_seen_at.desc()).limit(limit)
            if state:
                statement = statement.where(ErrorRecord.state == state)
            if component:
                statement = statement.where(ErrorRecord.component == component)
            return [
                error_out(r, full_context=full_context) for r in (await session.execute(statement)).scalars()
            ]

    async def transition(
        self, actor: Principal, error_id: UUID, to: str, resolution: str | None = None
    ) -> dict[str, Any]:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await self.recorder.transition(uow.session, error_id, actor, to, resolution, now)
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action=f"observability.error_{to}",
                    actor=actor,
                    resource=ResourceRef("observability_error", str(row.id)),
                    decision="allow",
                    result="success",
                    context={"component": row.component, "category": row.category},
                    sensitive=True,
                ),
            )
            return error_out(row, full_context=True)
