"""Community project API (T009, T011): projects with state, frozen rules, public funding totals, history
and notes (``marketplace.read``, granted to users — the contract's ``community.read`` belongs to another
module); funding (``marketplace.purchase`` + active account + acknowledgement);
the member's own fundings. Other funders' identities are never exposed."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.core.errors import Unavailable
from portalab.modules.marketplace.models import Project
from portalab.modules.marketplace.module import MarketplaceModule
from portalab.modules.marketplace.permissions import PURCHASE, READ
from portalab.modules.marketplace.projects.state import accepts_funding, accepts_votes

router = APIRouter(prefix="/api/v1", tags=["projects"])
SELF = "users.self.manage"


def marketplace_module(request: Request) -> MarketplaceModule:
    module = getattr(request.app.state, "marketplace_module", None)
    if not isinstance(module, MarketplaceModule):
        raise Unavailable("The Marketplace is not available.", code="marketplace.unavailable")
    return module


Module = Annotated[MarketplaceModule, Depends(marketplace_module)]
Reader = Annotated[Principal, require(READ)]
Funder = Annotated[Principal, require(PURCHASE)]
Me = Annotated[Principal, require(SELF)]


class ProjectTotalsOut(BaseModel):
    reserved: int
    consumed: int
    funders: int
    goal_amount: int | None


class ProjectHistoryOut(BaseModel):
    seq: int
    from_state: str | None
    to_state: str
    reason: str | None
    at: datetime


class ProjectNoteOut(BaseModel):
    state: str
    note: str
    at: datetime


class ProjectOut(BaseModel):
    id: UUID
    proposal_ref: str
    title: str
    state: str
    accepts_votes: bool
    accepts_funding: bool
    funding_rules: dict[str, Any] | None
    rules_frozen_at: datetime | None
    version: int
    updated_at: datetime
    totals: ProjectTotalsOut
    history: list[ProjectHistoryOut] = []
    notes: list[ProjectNoteOut] = []


class ProjectFundIn(BaseModel):
    amount: int = Field(ge=1, le=10_000_000)
    acknowledged: bool = False


class ProjectFundingOut(BaseModel):
    id: UUID
    project_id: UUID
    project_title: str
    project_state: str
    amount: int
    status: str
    reserved: int
    consumed: int
    released: int
    created_at: datetime


async def project_out(module: MarketplaceModule, project: Project, *, detail: bool = False) -> ProjectOut:
    async with module.database.session() as session:
        totals = await module.projects.totals(session, project.id)
    out = ProjectOut(
        id=project.id,
        proposal_ref=project.proposal_ref,
        title=project.title,
        state=project.state,
        accepts_votes=accepts_votes(project.state),
        accepts_funding=accepts_funding(project.state),
        funding_rules=project.funding_rules,
        rules_frozen_at=project.rules_frozen_at,
        version=project.version,
        updated_at=project.updated_at,
        totals=ProjectTotalsOut(**totals, goal_amount=project.goal_amount),
    )
    if detail:
        out.history = [
            ProjectHistoryOut(
                seq=h.seq, from_state=h.from_state, to_state=h.to_state, reason=h.reason, at=h.created_at
            )
            for h in await module.projects.history(project.id)
        ]
        out.notes = [
            ProjectNoteOut(state=n.state, note=n.public_note, at=n.created_at)
            for n in await module.projects.notes(project.id)
        ]
    return out


def _amounts(tranches: list[dict[str, Any]], status: str) -> int:
    return sum(int(t["amount"]) for t in tranches if t["status"] == status)


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(_: Reader, module: Module, state: str | None = None) -> list[ProjectOut]:
    return [await project_out(module, p) for p in await module.projects.all(state)]


class ProjectsSeenOut(BaseModel):
    previous: datetime | None = None  # when I had last opened them: what changed after is new to me


@router.post("/marketplace/projects/seen", response_model=ProjectsSeenOut)
async def projects_seen(principal: Reader, module: Module) -> ProjectsSeenOut:
    """#303: I opened the community projects — what was added or moved on is no longer new."""
    user = principal.acting_for or principal.user_id
    if user is None:
        return ProjectsSeenOut()
    return ProjectsSeenOut(previous=await module.projects.mark_seen(user))


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(_: Reader, project_id: UUID, module: Module) -> ProjectOut:
    return await project_out(module, await module.projects.get(project_id), detail=True)


@router.post("/projects/{project_id}/fund", response_model=ProjectFundingOut, status_code=201)
async def fund_project(
    principal: Funder,
    project_id: UUID,
    body: ProjectFundIn,
    module: Module,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)] = None,
) -> ProjectFundingOut:
    funding = await module.fundings.fund(
        principal,
        project_id,
        body.amount,
        acknowledged=body.acknowledged,
        request_key=idempotency_key or str(uuid4()),
    )
    project = await module.projects.get(funding.project_id)
    return funding_out(funding, project)


def funding_out(funding: Any, project: Project) -> ProjectFundingOut:
    return ProjectFundingOut(
        id=funding.id,
        project_id=project.id,
        project_title=project.title,
        project_state=project.state,
        amount=funding.amount,
        status=funding.status,
        reserved=_amounts(funding.tranches, "reserved"),
        consumed=_amounts(funding.tranches, "consumed"),
        released=_amounts(funding.tranches, "released"),
        created_at=funding.created_at,
    )


@router.get("/me/fundings", response_model=list[ProjectFundingOut])
async def my_fundings(principal: Me, module: Module) -> list[ProjectFundingOut]:
    user = principal.acting_for or principal.user_id
    assert user is not None
    return [funding_out(f, p) for f, p in await module.fundings.mine(user)]
