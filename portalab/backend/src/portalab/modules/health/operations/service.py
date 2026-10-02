"""Server operations (T020; R4b, FR-016..018): listed and executed through the service's
``server.operations`` provider. Every execution is sensitive (confirmation at the API), audited and
announced (``service.operation_performed``); an unreachable host yields an actionable error."""

from typing import Any

from portalab.capabilities.health import SERVER_OPERATIONS
from portalab.capabilities.results import Available
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import NotFound
from portalab.core.event_port import SubjectRef
from portalab.core.time import utc_now
from portalab.modules.health.common import OperationFailed, audit
from portalab.modules.health.state.service import StateService


class OperationsService:
    def __init__(self, state: StateService, audit_sink: AuditSink) -> None:
        self.state = state
        self.audit = audit_sink

    def provider(self, service_id: str) -> Any:
        for registration in self.state.capabilities.system_providers(SERVER_OPERATIONS):
            if registration.instance_ref == service_id:
                return registration.provider
        return None

    async def list(self, service_id: str) -> list[dict[str, Any]]:
        provider = self.provider(service_id)
        if provider is None:
            return []
        result = await provider.list_operations()
        if not isinstance(result, Available):
            raise OperationFailed(
                "The service's operations cannot be listed right now; check that its host is reachable."
            )
        return [
            {"key": op.key, "label": op.label, "description": op.description, "sensitive": op.sensitive}
            for op in result.value
        ]

    async def execute(
        self, actor: Principal, service_id: str, operation: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        provider = self.provider(service_id)
        known = {item["key"] for item in await self.list(service_id)}
        if provider is None or operation not in known:
            raise NotFound("This service has no such operation.", code="operation.not_found")
        result = await provider.execute(operation, params)
        ok = isinstance(result, Available)
        async with self.state.database.unit_of_work() as uow:
            published = await self.state.events.publish(
                uow.session,
                "service.operation_performed",
                {"service_id": service_id, "operation": operation, "result": "success" if ok else "failure"},
                occurred_at=utc_now(self.state.clock),
                actor=actor,
                subject=SubjectRef("service", service_id),
                source="health",
            )
            await audit(
                self.audit,
                uow.session,
                "service.operation_performed",
                actor,
                resource=ResourceRef("service", service_id),
                context={"operation": operation, "outcome": result.state},
                result="success" if ok else "failure",
                event_id=published.event_id,
            )
        if not ok:
            raise OperationFailed(
                "The operation could not be performed: the service's host did not answer. "
                "Check that it is running and reachable, then retry.",
                extensions={"outcome": result.state},
            )
        return {"operation": operation, "result": dict(result.value)}
