"""Automation action types (T036; spec 019 F14): ``connector.sync`` and ``connector.action``.

Declared through the owners' action contract (:mod:`portalab.capabilities.automation_actions`) with the
permission each requires and how a duplicate execution stays harmless. The permission is checked here too
(server side, for the acting principal — an automation never exceeds its user, CD-003).
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from portalab.capabilities.automation_actions import ActionRegistry, ActionType
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.errors import Forbidden, NotFound, ValidationFailed
from portalab.modules.connectors.permissions import SERVICES_MANAGE
from portalab.modules.connectors.services.common import ServiceDisabled, service_ref
from portalab.modules.connectors.services.manager import ServiceManager
from portalab.modules.connectors.sync.scheduler import SyncScheduler

OWNER = "module:connectors"


class ConnectorActions:
    def __init__(self, scheduler: SyncScheduler, authorizer: Authorizer) -> None:
        self.scheduler = scheduler
        self.manager: ServiceManager = scheduler.manager
        self.authorizer = authorizer

    async def _service_id(self, params: Mapping[str, Any], principal: Principal) -> UUID:
        try:
            service_id = UUID(str(params.get("service_id")))
        except ValueError as exc:
            raise ValidationFailed("service_id is required.", code="automation.invalid_params") from exc
        if not await self.authorizer.is_allowed(principal, SERVICES_MANAGE, service_ref(service_id)):
            raise Forbidden("The automation's user may not manage this service.")
        return service_id

    async def sync(self, params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        service_id = await self._service_id(params, principal)
        idempotency = params.get("idempotency_ref")
        async with self.manager.database.unit_of_work() as uow:
            row = await self.manager._row(uow.session, service_id)
            if row.state not in ("enabled", "error", "unavailable"):
                raise ServiceDisabled("This service is not enabled.")
            result = await self.scheduler.enqueue(
                uow.session,
                service_id,
                kind="manual",
                requested_by=principal.acting_for or principal.user_id,
                dedup_key=f"connectors.sync:{service_id}:automation:{idempotency}" if idempotency else None,
            )
        return {"job_id": str(result.job_id), "queued": result.created}

    async def action(self, params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        service_id = await self._service_id(params, principal)
        name = str(params.get("action", ""))
        async with self.manager.database.session() as session:
            row = await self.manager._row(session, service_id)
            if row.state != "enabled":
                raise ServiceDisabled("This service is not enabled.")
            connector = self.manager.connector(row.connector_key)
            handle = self.manager.handle(row)
        actions = connector.actions()
        if name not in actions:
            raise NotFound("This connector has no such action.", code="connector.action_not_found")
        result = await actions[name](handle, dict(params.get("arguments") or {}))
        return {"result": result}


def register_actions(registry: ActionRegistry, actions: ConnectorActions) -> None:
    registry.register(
        ActionType(
            key="connector.sync",
            description="Synchronize a service now",
            permission=SERVICES_MANAGE,
            idempotency="per-service advisory lock; optional idempotency_ref dedups the queued job",
            run=actions.sync,
            owner=OWNER,
            params_schema={"service_id": "uuid", "idempotency_ref": "string?"},
        )
    )
    registry.register(
        ActionType(
            key="connector.action",
            description="Run an action declared by a service's connector",
            permission=SERVICES_MANAGE,
            idempotency="connector actions must be idempotent; each declares how (connector manifest)",
            run=actions.action,
            owner=OWNER,
            params_schema={"service_id": "uuid", "action": "string", "arguments": "object?"},
        )
    )
