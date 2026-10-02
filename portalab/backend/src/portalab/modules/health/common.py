"""Problem codes and audit helper of the Health module."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import NotFound, Unavailable, ValidationFailed
from portalab.modules.health.observability import log


class MaintenanceNotFound(NotFound):
    default_code = "maintenance.not_found"


class InvalidWindow(ValidationFailed):
    default_code = "maintenance.invalid_window"


class OperationFailed(Unavailable):
    default_code = "operation.failed"
    default_title = "The operation could not be performed"


class AuditUnavailable(Unavailable):
    default_code = "audit.unavailable"
    default_title = "Audit unavailable"


async def audit(
    sink: AuditSink,
    session: AsyncSession | None,
    action: str,
    actor: Principal | None,
    *,
    resource: ResourceRef | None = None,
    context: Mapping[str, Any] | None = None,
    sensitive: bool = True,
    result: str = "success",
    event_id: UUID | None = None,
) -> None:
    try:
        await sink.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=resource,
                decision="allow",
                result=result,  # type: ignore[arg-type]
                context=dict(context or {}),
                sensitive=sensitive,
                event_id=event_id,
            ),
        )
    except Exception as exc:
        log.error("audit write failed", extra={"fields": {"action": action}})
        if sensitive:
            raise AuditUnavailable("The action was refused because it could not be audited.") from exc
