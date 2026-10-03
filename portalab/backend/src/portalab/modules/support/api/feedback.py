"""Feedback API (Slice B): forms, submissions, the staff review queue and explicit conversions."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Forbidden, Unavailable
from portalab.modules.support.api.incidents import support_module
from portalab.modules.support.api.tickets import ConfirmationRequired
from portalab.modules.support.conversion.service import PERMISSION, SENSITIVE
from portalab.modules.support.models import FeedbackItem
from portalab.modules.support.module import SupportModule

router = APIRouter(prefix="/api/v1", tags=["support"])
Module = Annotated[SupportModule, Depends(support_module)]
Submitter = Annotated[Principal, require("feedback.submit")]
Reader = Annotated[Principal, require("feedback.read")]


class FeedbackFormOut(BaseModel):
    key: str
    kind: str
    label: str
    fields: list[dict[str, Any]]
    version: int


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form_key: str = Field(max_length=60)
    values: dict[str, Any] = Field(default_factory=dict)


class FeedbackOut(BaseModel):
    id: UUID
    form_key: str
    form_version: int
    kind: str
    status: str
    payload: dict[str, Any]
    submitter_id: UUID | None
    created_at: datetime


class FeedbackConversionOut(BaseModel):
    target: str
    available: bool
    reason: str | None
    done: str | None


class FeedbackDetail(FeedbackOut):
    conversions: list[FeedbackConversionOut]


class FeedbackConvertIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_kind: Literal["ticket", "contribution", "feature_proposal", "community_project"]
    confirmation: str | None = None


def out(item: FeedbackItem) -> FeedbackOut:
    return FeedbackOut(
        id=item.id,
        form_key=item.form_key,
        form_version=item.form_version,
        kind=item.kind,
        status=item.status,
        payload=item.payload,
        submitter_id=item.submitter_id,
        created_at=item.created_at,
    )


@router.get("/feedback/forms", response_model=list[FeedbackFormOut])
async def forms(principal: Submitter, module: Module) -> list[FeedbackFormOut]:
    return [
        FeedbackFormOut(key=f.key, kind=f.kind, label=f.label, fields=f.fields, version=f.version)
        for f in await module.definitions.forms()
    ]


@router.post("/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def submit(principal: Submitter, body: FeedbackIn, module: Module) -> FeedbackOut:
    return out(await module.feedback.submit(principal, body.form_key, body.values))


@router.get("/support/feedback", response_model=list[FeedbackOut])
async def queue(
    principal: Reader,
    module: Module,
    status_filter: Annotated[str | None, Query(alias="status", max_length=12)] = None,
    kind: Annotated[str | None, Query(max_length=30)] = None,
) -> list[FeedbackOut]:
    return [out(i) for i in await module.feedback.listing(principal, status=status_filter, kind=kind)]


@router.get("/support/feedback/{feedback_id}", response_model=FeedbackDetail)
async def one(principal: Reader, feedback_id: UUID, module: Module) -> FeedbackDetail:
    item, _ = await module.feedback.get(principal, feedback_id)
    options = await module.conversion.options(principal, feedback_id)
    return FeedbackDetail(
        **out(item).model_dump(),
        conversions=[
            FeedbackConversionOut(target=o.target, available=o.available, reason=o.reason, done=o.done)
            for o in options
        ],
    )


@router.post("/support/feedback/{feedback_id}/convert")
async def convert(
    principal: Reader, feedback_id: UUID, body: FeedbackConvertIn, module: Module
) -> dict[str, Any]:
    target = body.target_kind
    if target in SENSITIVE:
        providers = module.capabilities.system_providers(CONFIRMATIONS)
        if not providers:
            raise Unavailable("Confirmations are not available.", code="authz.unavailable")
        confirmations = providers[0].provider
        resource, payload = ResourceRef("feedback", str(feedback_id)), {"target": target}
        if body.confirmation is None:
            issued = await confirmations.issue(principal, PERMISSION[target], resource, payload)
            raise ConfirmationRequired(
                "This conversion cannot be undone. Confirm to continue.", extensions={"confirmation": issued}
            )
        if not await confirmations.consume(
            body.confirmation, principal, PERMISSION[target], resource, payload
        ):
            raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")
    row = await module.conversion.convert(principal, feedback_id, target)
    async with module.database.unit_of_work() as uow:
        from portalab.core.audit_port import AuditRecord

        await module.audit.record(
            uow.session,
            AuditRecord(
                action="feedback.converted",
                actor=principal,
                resource=ResourceRef("feedback", str(feedback_id)),
                decision="allow",
                result="success",
                context={"target": target, "ref": row.target_ref},
                sensitive=True,
            ),
        )
    return {"target": target, "ref": row.target_ref}


@router.post("/support/feedback/{feedback_id}/{action}", response_model=FeedbackOut)
async def review(
    principal: Reader, feedback_id: UUID, action: Literal["review", "dismiss"], module: Module
) -> FeedbackOut:
    status_value = "reviewed" if action == "review" else "dismissed"
    return out(await module.feedback.set_status(principal, feedback_id, status_value))
