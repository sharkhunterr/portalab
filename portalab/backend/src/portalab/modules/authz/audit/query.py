"""Audit query/export (T021): allow-listed filters, cursor pagination by ``seq`` (newest first), context
redacted for viewers below the Admin level (only keys are shown), and every read is itself audited."""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.errors import BadRequest
from portalab.modules.authz.models import AuditEntry

FULL_CONTEXT_PERMISSION = "security.manage"  # reserved to the Admin
MAX_PAGE = 200
MAX_EXPORT = 10_000


@dataclass(frozen=True, slots=True)
class AuditFilters:
    action: str | None = None  # prefix match
    actor_user_id: UUID | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    decision: str | None = None
    since: datetime | None = None
    until: datetime | None = None

    def as_context(self) -> dict[str, Any]:
        return {key: str(value) for key, value in asdict(self).items() if value is not None}


def _apply(statement: Select[tuple[AuditEntry]], filters: AuditFilters) -> Select[tuple[AuditEntry]]:
    if filters.action:
        statement = statement.where(AuditEntry.action.startswith(filters.action, autoescape=True))
    if filters.actor_user_id:
        statement = statement.where(AuditEntry.actor_user_id == filters.actor_user_id)
    if filters.resource_type:
        statement = statement.where(AuditEntry.resource_type == filters.resource_type)
    if filters.resource_id:
        statement = statement.where(AuditEntry.resource_id == filters.resource_id)
    if filters.decision:
        statement = statement.where(AuditEntry.decision == filters.decision)
    if filters.since:
        statement = statement.where(AuditEntry.occurred_at >= filters.since)
    if filters.until:
        statement = statement.where(AuditEntry.occurred_at < filters.until)
    return statement


def serialize(entry: AuditEntry, *, full_context: bool) -> dict[str, Any]:
    context = entry.context if full_context else {"redacted": True, "keys": sorted(entry.context)}
    return {
        "seq": entry.seq,
        "id": str(entry.id),
        "occurred_at": entry.occurred_at.isoformat(),
        "actor_user_id": str(entry.actor_user_id) if entry.actor_user_id else None,
        "actor_kind": entry.actor_kind,
        "acting_for": str(entry.acting_for) if entry.acting_for else None,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "scope": entry.scope,
        "decision": entry.decision,
        "result": entry.result,
        "context": context,
        "correlation_id": entry.correlation_id,
    }


class AuditQuery:
    def __init__(self, database: Database, audit: AuditSink, authorizer: Authorizer) -> None:
        self.database = database
        self.audit = audit
        self.authorizer = authorizer

    async def _full_context(self, viewer: Principal) -> bool:
        return await self.authorizer.is_allowed(viewer, FULL_CONTEXT_PERMISSION)

    async def _audit_read(self, viewer: Principal, action: str, filters: AuditFilters, count: int) -> None:
        await self.audit.record(
            None,
            AuditRecord(
                action=action,
                actor=viewer,
                decision="allow",
                result="success",
                context={"filters": filters.as_context(), "returned": count},
                sensitive=True,
            ),
        )

    async def search(
        self, viewer: Principal, filters: AuditFilters, *, limit: int, cursor: str | None
    ) -> tuple[list[dict[str, Any]], str | None]:
        limit = max(1, min(limit, MAX_PAGE))
        statement = _apply(select(AuditEntry), filters).order_by(AuditEntry.seq.desc()).limit(limit + 1)
        if cursor:
            try:
                statement = statement.where(AuditEntry.seq < int(cursor))
            except ValueError as exc:
                raise BadRequest("Invalid cursor.", code="pagination.invalid_cursor") from exc
        async with self.database.session() as session:
            rows = list((await session.execute(statement)).scalars())
        full = await self._full_context(viewer)
        page = rows[:limit]
        await self._audit_read(viewer, "audit.read", filters, len(page))
        next_cursor = str(page[-1].seq) if len(rows) > limit else None
        return [serialize(entry, full_context=full) for entry in page], next_cursor

    async def export(self, viewer: Principal, filters: AuditFilters) -> list[dict[str, Any]]:
        statement = _apply(select(AuditEntry), filters).order_by(AuditEntry.seq).limit(MAX_EXPORT)
        async with self.database.session() as session:
            rows = list((await session.execute(statement)).scalars())
        full = await self._full_context(viewer)
        await self._audit_read(viewer, "audit.exported", filters, len(rows))
        return [serialize(entry, full_context=full) for entry in rows]
