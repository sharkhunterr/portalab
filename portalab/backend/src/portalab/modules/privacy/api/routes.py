"""Privacy API (T014, T029, T038): admin visibility policies, privacy center, service purge."""

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.privacy.models import VisibilityPolicy
from portalab.modules.privacy.module import PrivacyModule
from portalab.modules.privacy.policies.service import PolicyRequest

router = APIRouter(prefix="/api/v1", tags=["privacy"])

LevelName = Literal["public", "community", "leaderboard", "private"]


def privacy_module(request: Request) -> PrivacyModule:
    module = getattr(request.app.state, "privacy_module", None)
    if not isinstance(module, PrivacyModule):
        raise Unavailable("Privacy is not available.", code="privacy.unavailable")
    return module


Module = Annotated[PrivacyModule, Depends(privacy_module)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicyIn(Strict):
    datum_class: str = Field(min_length=1, max_length=64)
    mode: Literal["user_choice", "force_visible", "force_private"]
    level: LevelName | None = None
    subject_user_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=256)
    ends_at: datetime | None = None


class PolicyOut(BaseModel):
    id: UUID
    datum_class: str
    mode: str
    level: str | None
    subject_user_id: UUID | None
    reason: str
    set_at: datetime
    ends_at: datetime | None


class DatumOut(BaseModel):
    datum_class: str
    owner: str
    classification: str
    description: str
    default_level: str
    effective_level: str
    locked_by_policy: bool
    user_choosable: bool
    retention_days: int | None


class PrivacyInventory(BaseModel):
    data: list[DatumOut]
    export_endpoint: str = "/api/v1/me/export"
    deletion_endpoint: str = "/api/v1/me/deletion"


class PreferenceIn(Strict):
    level: LevelName
    datum_ref: str | None = Field(default=None, max_length=64)


class PreferenceOut(BaseModel):
    stored: bool = True
    effective_now: bool


class PurgeIn(Strict):
    confirmation: str | None = Field(default=None, max_length=128)


class PurgeOut(BaseModel):
    service_id: str
    job_id: str


def _policy(policy: VisibilityPolicy) -> PolicyOut:
    return PolicyOut(
        id=policy.id,
        datum_class=policy.datum_class,
        mode=policy.mode,
        level=policy.level,
        subject_user_id=policy.subject_user_id,
        reason=policy.reason,
        set_at=policy.set_at,
        ends_at=policy.ends_at,
    )


@router.get("/privacy/policies", response_model=list[PolicyOut])
async def list_policies(
    module: Module,
    subject_user_id: Annotated[UUID | None, Query()] = None,
    principal: Principal = require("privacy.manage"),
) -> list[PolicyOut]:
    return [_policy(policy) for policy in await module.policies.list_active(subject_user_id)]


@router.post(
    "/privacy/policies",
    status_code=status.HTTP_201_CREATED,
    response_model=PolicyOut,
    responses={409: {"description": "privacy.policy_exists"}},
)
async def apply_policy(
    body: PolicyIn, module: Module, principal: Principal = require("privacy.manage")
) -> PolicyOut:
    request = PolicyRequest(
        datum_class=body.datum_class,
        mode=body.mode,
        reason=body.reason,
        subject_user_id=body.subject_user_id,
        level=body.level,
        ends_at=body.ends_at,
    )
    return _policy(await module.policies.apply(principal, request))


@router.delete("/privacy/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_policy(
    policy_id: UUID, module: Module, principal: Principal = require("privacy.manage")
) -> Response:
    await module.policies.remove(principal, policy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/privacy", response_model=PrivacyInventory)
async def my_privacy(module: Module, principal: Principal = require("users.self.manage")) -> PrivacyInventory:
    assert principal.user_id is not None
    entries = await module.center.inventory(principal.user_id)
    return PrivacyInventory(data=[DatumOut(**asdict(entry)) for entry in entries])


@router.put(
    "/me/privacy/visibility/{datum_class}",
    response_model=PreferenceOut,
    responses={409: {"description": "privacy.preference_not_supported"}},
)
async def set_my_visibility(
    datum_class: str, body: PreferenceIn, module: Module, principal: Principal = require("users.self.manage")
) -> PreferenceOut:
    assert principal.user_id is not None
    effective = await module.center.set_preference(principal.user_id, datum_class, body.datum_ref, body.level)
    return PreferenceOut(effective_now=effective)


@router.post(
    "/services/{service_id}/purge",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PurgeOut,
    responses={409: {"description": "authz.confirmation_required (carries `confirmation`)"}},
)
async def purge_service(
    service_id: Annotated[str, Path(max_length=128)],
    body: PurgeIn,
    module: Module,
    principal: Principal = require("services.purge"),
) -> PurgeOut:
    requested = await module.purge.request(principal, service_id, body.confirmation)
    return PurgeOut(service_id=requested.service_id, job_id=requested.job_id)
