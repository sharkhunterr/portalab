"""Server operations API (T020): ``services.manage``; executing is sensitive — a single-use confirmation
bound to the service, the operation and its parameters is required, and every attempt is audited."""

from typing import Annotated, Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, Unavailable
from portalab.modules.health.api.common import Module
from portalab.modules.health.permissions import SERVICES_MANAGE

router = APIRouter(prefix="/api/v1", tags=["health"])


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


class OperationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    params: dict[str, Any] = Field(default_factory=dict)
    confirmation: str | None = Field(default=None, max_length=128)


@router.get("/services/{service_id}/operations")
async def list_operations(
    _: Annotated[Principal, require(SERVICES_MANAGE)], service_id: str, module: Module
) -> dict[str, Any]:
    return {"items": await module.operations.list(service_id)}


@router.post(
    "/services/{service_id}/operations/{operation}",
    responses={409: {"description": "authz.confirmation_required (carries `confirmation`)"}},
)
async def execute(
    principal: Annotated[Principal, require(SERVICES_MANAGE)],
    service_id: str,
    operation: str,
    body: OperationIn,
    module: Module,
) -> dict[str, Any]:
    providers = module.capabilities.system_providers(CONFIRMATIONS)
    if not providers:
        raise Unavailable("Confirmations are not available.", code="authz.unavailable")
    confirmations = providers[0].provider
    resource = ResourceRef("service", service_id)
    payload = {"operation": operation, "params": body.params}
    if body.confirmation is None:
        issued = await confirmations.issue(principal, SERVICES_MANAGE, resource, payload)
        raise ConfirmationRequired(
            "Server operations act on the real host. Confirm to continue.",
            extensions={"confirmation": issued},
        )
    if not await confirmations.consume(body.confirmation, principal, SERVICES_MANAGE, resource, payload):
        raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")
    return await module.operations.execute(principal, service_id, operation, body.params)
