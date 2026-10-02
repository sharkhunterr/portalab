"""``AuditSink`` port — records of sensitive actions (CD-013; spec 003 contracts "AuditSink port").

``record(...)`` is called **inside the caller's transaction** so the audit entry commits with the action it
describes. For a *sensitive* action an audit failure must fail the action (fail closed); for other records
the failure is logged and counted. Spec 003 provides the append-only store (``audit.audit_entries``) and the
Audit/Security step (021) completes it; until then :class:`LogAuditSink` writes structured log records.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.logging import get_correlation_id, get_logger, redact

Decision = Literal["allow", "deny", "n/a"]
Result = Literal["success", "failure", "n/a"]


@dataclass(frozen=True, slots=True)
class AuditRecord:
    action: str
    actor: Principal | None
    resource: ResourceRef | None = None
    decision: Decision = "n/a"
    result: Result = "success"
    context: Mapping[str, Any] = field(default_factory=dict)
    sensitive: bool = False
    event_id: UUID | None = None  # the domain event describing the same action (spec 007, CD-013)


class AuditError(RuntimeError):
    """The audit entry could not be written; a sensitive action must then be refused."""


class AuditSink(Protocol):
    async def record(self, session: AsyncSession | None, entry: AuditRecord) -> None: ...


class LogAuditSink:
    """Interim sink: one structured ``audit`` log line per record (context redacted, ids only)."""

    def __init__(self) -> None:
        self._log = get_logger("portalab.audit")

    async def record(self, session: AsyncSession | None, entry: AuditRecord) -> None:
        actor = entry.actor
        self._log.info(
            "audit",
            extra={
                "fields": {
                    "action": entry.action,
                    "actor_id": str(actor.user_id) if actor and actor.user_id else None,
                    "actor_kind": actor.channel if actor else "system",
                    "acting_for": str(actor.acting_for) if actor and actor.acting_for else None,
                    "resource_type": entry.resource.kind if entry.resource else None,
                    "resource_id": entry.resource.id if entry.resource else None,
                    "decision": entry.decision,
                    "result": entry.result,
                    "sensitive": entry.sensitive,
                    "context": redact(dict(entry.context)),
                    "correlation_id": get_correlation_id(),
                }
            },
        )
