"""Requests to handle (027): a member follows the requests their purchases opened (a special request, a
service's access); administrators (``marketplace.manage``) see the open ones by deadline, start them, mark
them done — for a service, creating the account if they wish — or decline them (the Coins come back)."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.marketplace.api.projects import Module
from portalab.modules.marketplace.permissions import MANAGE, READ
from portalab.modules.marketplace.requests.service import RequestView

router = APIRouter(prefix="/api/v1", tags=["marketplace-requests"])
Reader = Annotated[Principal, require(READ)]
Manager = Annotated[Principal, require(MANAGE)]


class MarketplaceRequestOut(BaseModel):
    id: UUID
    kind: str
    state: str
    product_key: str
    product_name: str
    user_id: UUID
    user_name: str | None
    details: dict[str, Any]
    form: list[dict[str, Any]]
    due_at: datetime
    overdue: bool
    note: str | None
    decided_at: datetime | None
    created_at: datetime


class MarketplaceRequestDecisionIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
    create_account: bool = False  # a service's access: create the account in the identity provider


class MarketplaceRequestCountOut(BaseModel):
    open: int
    overdue: int


def request_out(view: RequestView) -> MarketplaceRequestOut:
    return MarketplaceRequestOut(
        id=view.id,
        kind=view.kind,
        state=view.state,
        product_key=view.product_key,
        product_name=view.product_name,
        user_id=view.user_id,
        user_name=view.user_name,
        details=view.details,
        form=view.form,
        due_at=view.due_at,
        overdue=view.overdue,
        note=view.note,
        decided_at=view.decided_at,
        created_at=view.created_at,
    )


@router.get("/me/marketplace/requests", response_model=list[MarketplaceRequestOut])
async def my_requests(principal: Reader, module: Module) -> list[MarketplaceRequestOut]:
    user = principal.acting_for or principal.user_id
    assert user is not None
    return [request_out(v) for v in await module.requests.mine(user)]


@router.get("/admin/marketplace/requests", response_model=list[MarketplaceRequestOut])
async def requests_queue(
    principal: Manager, module: Module, settled: Annotated[bool, Query()] = False
) -> list[MarketplaceRequestOut]:
    views = await module.requests.queue(principal.user_id, open_only=not settled)
    return [request_out(v) for v in views]


@router.get("/admin/marketplace/requests/count", response_model=MarketplaceRequestCountOut)
async def requests_count(principal: Manager, module: Module) -> MarketplaceRequestCountOut:
    total, overdue = await module.requests.open_count()
    return MarketplaceRequestCountOut(open=total, overdue=overdue)


@router.post("/admin/marketplace/requests/{request_id}/{action}", response_model=MarketplaceRequestOut)
async def decide_request(
    principal: Manager,
    request_id: UUID,
    action: Literal["start", "done", "decline"],
    body: MarketplaceRequestDecisionIn,
    module: Module,
) -> MarketplaceRequestOut:
    view = await module.requests.decide(principal, request_id, action, body.note, body.create_account)
    return request_out(view)
