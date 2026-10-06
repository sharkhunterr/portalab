"""Feedback API (Slice B): forms, submissions, the staff review queue and explicit conversions."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
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
    description: str = ""
    icon: str | None = None
    requested: bool = False
    opens_at: datetime | None = None
    closes_at: datetime | None = None


class FeedbackRequestOut(BaseModel):
    form: FeedbackFormOut
    answered: bool


class FeedbackReplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)


class FeedbackFieldResultOut(BaseModel):
    key: str
    label: str
    type: str
    answers: int
    average: float | None = None
    counts: dict[str, int] | None = None
    latest: list[str] | None = None


class FeedbackResultsOut(BaseModel):
    form: str
    label: str
    total: int
    fields: list[FeedbackFieldResultOut]


def form_out(f: Any) -> FeedbackFormOut:
    return FeedbackFormOut(
        key=f.key,
        kind=f.kind,
        label=f.label,
        fields=f.fields,
        version=f.version,
        description=f.description or "",
        icon=f.icon,
        requested=f.requested,
        opens_at=f.opens_at,
        closes_at=f.closes_at,
    )


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
    reply: str | None = None
    replied_at: datetime | None = None
    submitter_name: str | None = None  # staff views only (027)
    form_label: str | None = None


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
        reply=item.reply,
        replied_at=item.replied_at,
    )


@router.get("/feedback/forms", response_model=list[FeedbackFormOut])
async def forms(principal: Submitter, module: Module) -> list[FeedbackFormOut]:
    # requests are answered from « your opinion is asked », not offered as everyday forms
    return [form_out(f) for f in await module.definitions.forms() if not f.requested]


@router.get("/me/feedback/requests", response_model=list[FeedbackRequestOut])
async def my_requests(principal: Submitter, module: Module) -> list[FeedbackRequestOut]:
    """027: the requests open now and whether I already answered each."""
    return [
        FeedbackRequestOut(form=form_out(f), answered=answered)
        for f, answered in await module.feedback.open_requests(principal)
    ]


@router.get("/me/feedback", response_model=list[FeedbackOut])
async def my_feedback(principal: Submitter, module: Module) -> list[FeedbackOut]:
    """027: what I sent, its status and the staff reply."""
    return [out(i) for i in await module.feedback.mine(principal)]


@router.post("/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def submit(principal: Submitter, body: FeedbackIn, module: Module) -> FeedbackOut:
    return out(await module.feedback.submit(principal, body.form_key, body.values))


@router.get("/support/feedback", response_model=list[FeedbackOut])
async def queue(
    principal: Reader,
    module: Module,
    status_filter: Annotated[str | None, Query(alias="status", max_length=12)] = None,
    kind: Annotated[str | None, Query(max_length=30)] = None,
    form: Annotated[str | None, Query(max_length=60)] = None,
) -> list[FeedbackOut]:
    items = [i for i in await module.feedback.listing(principal, status=status_filter, kind=kind)]
    return await _named(module, [out(i) for i in items if form is None or i.form_key == form])


async def _named(module: Any, rows: list[FeedbackOut]) -> list[FeedbackOut]:
    """027: staff see who wrote and with which form (names from the identity directory)."""
    labels = {f.key: f.label for f in await module.definitions.forms(enabled_only=False)}
    names: dict[UUID, str | None] = {}
    directory = module.capabilities.system_providers(DIRECTORY)
    for row in rows:
        if row.submitter_id is not None and row.submitter_id not in names and directory:
            try:
                summary = await directory[0].provider.get_user_summary(row.submitter_id)
                names[row.submitter_id] = summary.display_name if summary else None
            except Exception:
                names[row.submitter_id] = None
        row.submitter_name = names.get(row.submitter_id) if row.submitter_id else None
        row.form_label = labels.get(row.form_key)
    return rows


@router.get("/support/feedback/results/{form_key}", response_model=FeedbackResultsOut)
async def results(principal: Reader, form_key: str, module: Module) -> FeedbackResultsOut:
    """027: a form's (or a request's) answers summed up."""
    return FeedbackResultsOut.model_validate(await module.feedback.results(principal, form_key[:60]))


@router.get("/support/feedback/{feedback_id}", response_model=FeedbackDetail)
async def one(principal: Reader, feedback_id: UUID, module: Module) -> FeedbackDetail:
    item, _ = await module.feedback.get(principal, feedback_id)
    options = await module.conversion.options(principal, feedback_id)
    [named] = await _named(module, [out(item)])
    return FeedbackDetail(
        **named.model_dump(),
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


@router.post("/support/feedback/{feedback_id}/reply", response_model=FeedbackOut)
async def reply(principal: Reader, feedback_id: UUID, body: FeedbackReplyIn, module: Module) -> FeedbackOut:
    """027: answer the member (shown in their feedback list, with a notification)."""
    [named] = await _named(module, [out(await module.feedback.reply(principal, feedback_id, body.text))])
    return named


@router.post("/support/feedback/{feedback_id}/{action}", response_model=FeedbackOut)
async def review(
    principal: Reader, feedback_id: UUID, action: Literal["review", "dismiss"], module: Module
) -> FeedbackOut:
    status_value = "reviewed" if action == "review" else "dismissed"
    return out(await module.feedback.set_status(principal, feedback_id, status_value))
