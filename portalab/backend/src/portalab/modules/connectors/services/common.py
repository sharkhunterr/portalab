"""Shared pieces of the connectors services: problem codes, audit (fail-closed) and event helpers."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, NotFound, Unavailable, ValidationFailed
from portalab.core.event_port import EventPublisher, PublishResult, SubjectRef
from portalab.modules.connectors.observability import log

SOURCE = "connectors"


class ServiceNotFound(NotFound):
    default_code = "service.not_found"


class ConnectorNotFound(NotFound):
    default_code = "connector.not_found"


class ConnectorIncompatible(Conflict):
    default_code = "connector.incompatible"
    default_title = "Connector incompatible"


class ConnectionTestFailed(Conflict):
    default_code = "connector.test_failed"
    default_title = "Connection test failed"


class SyncInProgress(Conflict):
    default_code = "service.sync_in_progress"
    default_title = "A synchronization is already running"


class ServiceDisabled(Conflict):
    default_code = "service.disabled"
    default_title = "The service is not enabled"


class InvalidTransition(Conflict):
    default_code = "service.invalid_transition"
    default_title = "This state change is not allowed"


class InvalidServiceConfig(ValidationFailed):
    default_code = "service.invalid_config"


class AuditUnavailable(Unavailable):
    default_code = "audit.unavailable"
    default_title = "Audit unavailable"


def service_ref(service_id: UUID | str) -> ResourceRef:
    return ResourceRef(kind="service", id=str(service_id))


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
    """Audit inside the caller's transaction; a failure refuses a sensitive action (fail closed)."""
    entry = AuditRecord(
        action=action,
        actor=actor,
        resource=resource,
        decision="allow",
        result=result,  # type: ignore[arg-type]
        context=dict(context or {}),
        sensitive=sensitive,
        event_id=event_id,
    )
    try:
        await sink.record(session, entry)
    except Exception as exc:
        log.error("audit write failed", extra={"fields": {"action": action, "sensitive": sensitive}})
        if sensitive:
            raise AuditUnavailable("The action was refused because it could not be audited.") from exc


async def publish(
    events: EventPublisher,
    session: AsyncSession,
    event_type: str,
    payload: Mapping[str, Any],
    *,
    service_id: UUID | str | None,
    actor: Principal | None,
    occurred_at: datetime,
) -> PublishResult:
    return await events.publish(
        session,
        event_type,
        payload,
        occurred_at=occurred_at,
        actor=actor,
        subject=SubjectRef("service", str(service_id)) if service_id is not None else None,
        source=SOURCE,
    )
