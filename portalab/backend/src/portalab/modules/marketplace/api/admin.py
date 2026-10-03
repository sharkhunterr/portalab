"""Project administration (T009): ``projects.manage`` (Admin; sensitive, audited). Validating, rejecting,
abandoning and releasing move or consume members' Coins, so they also need a confirmation."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Conflict, Forbidden, Unavailable
from portalab.modules.marketplace.api.projects import Module, ProjectOut, project_out
from portalab.modules.marketplace.permissions import PROJECTS_MANAGE

router = APIRouter(prefix="/api/v1", tags=["projects-admin"])
Manager = Annotated[Principal, require(PROJECTS_MANAGE)]
CONFIRMED = frozenset({"development", "rejected", "abandoned", "released"})


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


class ProjectTransitionIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=4000)
    version: int | None = None
    confirmation: str | None = None


class ProjectOpenIn(ProjectTransitionIn):
    rules: dict[str, Any] = Field(default_factory=dict)


class ProjectValidateIn(ProjectTransitionIn):
    approve: bool


class ProjectMoveIn(ProjectTransitionIn):
    to: Literal["validation", "development", "beta", "released"]


class ProjectAdminFundingOut(BaseModel):
    id: UUID
    user_id: UUID
    amount: int
    status: str
    created_at: datetime


async def _confirm(
    module: Any, principal: Principal, project_id: UUID, target: str, token: str | None
) -> None:
    if target not in CONFIRMED:
        return
    providers = module.capabilities.system_providers(CONFIRMATIONS)
    if not providers:
        raise Unavailable("Confirmations are not available.", code="authz.unavailable")
    confirmations = providers[0].provider
    resource = ResourceRef("project", str(project_id))
    payload = {"project": str(project_id), "to": target}
    if token is None:
        issued = await confirmations.issue(principal, PROJECTS_MANAGE, resource, payload)
        raise ConfirmationRequired(
            "This decision moves members' Coins. Confirm to continue.", extensions={"confirmation": issued}
        )
    if not await confirmations.consume(token, principal, PROJECTS_MANAGE, resource, payload):
        raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")


async def _move(
    module: Any, principal: Principal, project_id: UUID, target: str, body: ProjectTransitionIn, **extra: Any
) -> ProjectOut:
    await _confirm(module, principal, project_id, target, body.confirmation)
    project = await module.transition(
        principal,
        project_id,
        target,
        reason=body.reason,
        note=body.note,
        expected_version=body.version,
        **extra,
    )
    return await project_out(module, project, detail=True)


@router.get("/admin/projects/{project_id}/fundings", response_model=list[ProjectAdminFundingOut])
async def project_fundings(_: Manager, project_id: UUID, module: Module) -> list[ProjectAdminFundingOut]:
    await module.projects.get(project_id)
    return [
        ProjectAdminFundingOut(
            id=f.id, user_id=f.user_id, amount=f.amount, status=f.status, created_at=f.created_at
        )
        for f in await module.fundings.of_project(project_id)
    ]


@router.post("/admin/projects/{project_id}/promote", response_model=ProjectOut)
async def promote(
    principal: Manager, project_id: UUID, body: ProjectTransitionIn, module: Module
) -> ProjectOut:
    return await _move(module, principal, project_id, "proposal", body)


@router.post("/admin/projects/{project_id}/open", response_model=ProjectOut)
async def open_project(
    principal: Manager, project_id: UUID, body: ProjectOpenIn, module: Module
) -> ProjectOut:
    rules = {**module.config.funding_default_rules, **body.rules}
    return await _move(module, principal, project_id, "open", body, rules=rules)


@router.post("/admin/projects/{project_id}/validate", response_model=ProjectOut)
async def validate(
    principal: Manager, project_id: UUID, body: ProjectValidateIn, module: Module
) -> ProjectOut:
    return await _move(module, principal, project_id, "development" if body.approve else "rejected", body)


@router.post("/admin/projects/{project_id}/transition", response_model=ProjectOut)
async def move(principal: Manager, project_id: UUID, body: ProjectMoveIn, module: Module) -> ProjectOut:
    return await _move(module, principal, project_id, body.to, body)


@router.post("/admin/projects/{project_id}/abandon", response_model=ProjectOut)
async def abandon(
    principal: Manager, project_id: UUID, body: ProjectTransitionIn, module: Module
) -> ProjectOut:
    return await _move(module, principal, project_id, "abandoned", body)


@router.post("/admin/projects/{project_id}/reject", response_model=ProjectOut)
async def reject(
    principal: Manager, project_id: UUID, body: ProjectTransitionIn, module: Module
) -> ProjectOut:
    return await _move(module, principal, project_id, "rejected", body)
