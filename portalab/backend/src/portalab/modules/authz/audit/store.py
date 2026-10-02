"""``AuditSink`` implementation over ``audit.audit_entries`` (T028; CD-013).

Entries are appended in the caller's transaction when a session is given (the entry commits with the action)
or in their own transaction otherwise. Context is redacted with the kernel redaction and capped at
``authz.auditContextMaxBytes``; secrets never reach the table. Callers decide the failure policy: a
sensitive action whose audit write fails is refused (fail closed).
"""

import json
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.audit_port import AuditError, AuditRecord
from portalab.core.db import Database
from portalab.core.logging import get_correlation_id, redact
from portalab.core.time import Clock, utc_now
from portalab.modules.authz.models import AuditEntry
from portalab.modules.authz.observability import log, metrics


def _actor(entry: AuditRecord) -> tuple[Any, str, Any]:
    actor = entry.actor
    if actor is None:
        return None, "anonymous", None
    if actor.channel == "system":
        return None, "system", None
    if actor.user_id is None and actor.acting_for is None:
        return None, "anonymous", None
    return actor.user_id, actor.channel, actor.acting_for


def bounded_context(context: dict[str, Any], max_bytes: int) -> dict[str, Any]:
    safe = redact(dict(context))
    encoded = json.dumps(safe, default=str, ensure_ascii=False)
    if len(encoded.encode("utf-8")) <= max_bytes:
        return json.loads(encoded)  # type: ignore[no-any-return]
    return {"truncated": True, "keys": sorted(str(key) for key in safe)[:50]}


class DatabaseAuditSink:
    def __init__(
        self, database: Database, *, max_context_bytes: int = 4096, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.max_context_bytes = max_context_bytes
        self.clock = clock

    def _values(self, entry: AuditRecord) -> dict[str, Any]:
        actor_user_id, actor_kind, acting_for = _actor(entry)
        now = utc_now(self.clock)
        return {
            "occurred_at": now,
            "received_at": now,
            "actor_user_id": actor_user_id,
            "actor_kind": actor_kind,
            "acting_for": acting_for,
            "action": entry.action,
            "resource_type": entry.resource.kind if entry.resource else None,
            "resource_id": entry.resource.id if entry.resource else None,
            "scope": str(entry.context.get("scope")) if entry.context.get("scope") else None,
            "decision": entry.decision,
            "result": entry.result,
            "context": bounded_context(dict(entry.context), self.max_context_bytes),
            "correlation_id": get_correlation_id(),
        }

    async def record(self, session: AsyncSession | None, entry: AuditRecord) -> None:
        try:
            values = self._values(entry)
            if session is not None:
                async with session.begin_nested():
                    await session.execute(insert(AuditEntry).values(**values))
            else:
                async with self.database.unit_of_work() as uow:
                    await uow.session.execute(insert(AuditEntry).values(**values))
        except Exception as exc:
            metrics.increment("authz.audit.write_failed")
            log.error("audit write failed", extra={"fields": {"action": entry.action}})
            raise AuditError("audit entry could not be written") from exc
