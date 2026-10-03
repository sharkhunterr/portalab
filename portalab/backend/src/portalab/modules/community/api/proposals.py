"""Proposals, votes and participation API (T023, T026; slice D). Proposing needs ``community.propose``;
voting is the **active-account invariant** (allow-listed in the permission matrix: ``community.read`` plus
``is_active_account``, never a role permission); participating needs ``community.participate``; moderation
needs ``community.moderate`` (audited). Voter identities are never returned — only counts and the viewer's
own vote."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from portalab.core.authorization import require
from portalab.core.authz_port import Principal
from portalab.modules.community.api.public import Module
from portalab.modules.community.models import Proposal
from portalab.modules.community.module import CommunityModule
from portalab.modules.community.permissions import MODERATE, PARTICIPATE, PROPOSE, READ
from portalab.modules.community.preferences import PROJECTS, shown
from portalab.modules.community.proposals.lifecycle import lifecycle_summary
from portalab.modules.community.proposals.service import user_of

router = APIRouter(prefix="/api/v1", tags=["community"])
Reader = Annotated[Principal, require(READ)]
Proposer = Annotated[Principal, require(PROPOSE)]
Participant = Annotated[Principal, require(PARTICIPATE)]
Moderator = Annotated[Principal, require(MODERATE)]


class CommunityProposalIn(BaseModel):
    kind: Literal["project", "feature"] = "project"
    title: str = Field(min_length=1, max_length=200)
    body_md: str = Field(default="", max_length=20_000)
    tags: list[str] = Field(default_factory=list, max_length=8)


class CommunityProposalEditIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body_md: str = Field(default="", max_length=20_000)
    tags: list[str] = Field(default_factory=list, max_length=8)


class CommunityHelpIn(BaseModel):
    help_wanted: bool
    note: str | None = Field(default=None, max_length=500)


class CommunityParticipateIn(BaseModel):
    role: Literal["contributor", "tester", "helper"]
    note: str | None = Field(default=None, max_length=500)


class CommunityModerationIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class CommunityPersonOut(BaseModel):
    id: UUID
    display_name: str | None


class CommunityProposalOut(BaseModel):
    id: UUID
    kind: str
    title: str
    body_md: str | None
    rendered_html: str
    tags: list[str]
    status: str
    help_wanted: bool
    help_note: str | None
    proposer: CommunityPersonOut | None
    mine: bool
    votes: int
    my_vote: bool
    lifecycle: dict[str, Any]
    created_at: datetime


class CommunityVoteOut(BaseModel):
    votes: int
    my_vote: bool


class CommunityParticipationOut(BaseModel):
    id: UUID
    role: str
    note: str | None
    member: CommunityPersonOut | None
    mine: bool
    recognized: bool


async def proposal_out(
    module: CommunityModule, viewer: Principal, proposal: Proposal
) -> CommunityProposalOut:
    me = user_of(viewer)
    proposer: CommunityPersonOut | None = None
    if proposal.proposer_id is not None and (
        proposal.proposer_id == me
        or await shown(module.visibility, viewer, proposal.proposer_id, PROJECTS, True)
    ):
        proposer = CommunityPersonOut(
            id=proposal.proposer_id, display_name=await module.display_name(proposal.proposer_id)
        )
    counts = await module.votes.counts([proposal.id])
    return CommunityProposalOut(
        id=proposal.id,
        kind=proposal.kind,
        title=proposal.title,
        body_md=proposal.body_md if proposal.proposer_id == me else None,
        rendered_html=proposal.rendered_html,
        tags=list(proposal.tags),
        status=proposal.status,
        help_wanted=proposal.help_wanted,
        help_note=proposal.help_note,
        proposer=proposer,
        mine=proposal.proposer_id == me,
        votes=counts.get(proposal.id, 0),
        my_vote=proposal.id in await module.votes.voted(me, [proposal.id]),
        lifecycle=await lifecycle_summary(module.proposals, proposal),
        created_at=proposal.created_at,
    )


@router.get("/community/proposals", response_model=list[CommunityProposalOut])
async def list_proposals(
    principal: Reader, module: Module, mine: bool = False, status: str | None = None
) -> list[CommunityProposalOut]:
    rows = await module.proposals.listing(principal, mine=mine, status=status)
    return [await proposal_out(module, principal, p) for p in rows]


@router.post("/community/proposals", response_model=CommunityProposalOut, status_code=201)
async def create_proposal(
    principal: Proposer, body: CommunityProposalIn, module: Module
) -> CommunityProposalOut:
    proposal = await module.proposals.create(principal, body.kind, body.title, body.body_md, tags=body.tags)
    return await proposal_out(module, principal, proposal)


@router.get("/community/proposals/{proposal_id}", response_model=CommunityProposalOut)
async def get_proposal(principal: Reader, proposal_id: UUID, module: Module) -> CommunityProposalOut:
    return await proposal_out(module, principal, await module.proposals.get(principal, proposal_id))


@router.patch("/community/proposals/{proposal_id}", response_model=CommunityProposalOut)
async def edit_proposal(
    principal: Proposer, proposal_id: UUID, body: CommunityProposalEditIn, module: Module
) -> CommunityProposalOut:
    proposal = await module.proposals.edit(principal, proposal_id, body.title, body.body_md, body.tags)
    return await proposal_out(module, principal, proposal)


@router.post("/community/proposals/{proposal_id}/withdraw", response_model=CommunityProposalOut)
async def withdraw_proposal(principal: Proposer, proposal_id: UUID, module: Module) -> CommunityProposalOut:
    return await proposal_out(module, principal, await module.proposals.withdraw(principal, proposal_id))


@router.put("/community/proposals/{proposal_id}/help", response_model=CommunityProposalOut)
async def ask_help(
    principal: Reader, proposal_id: UUID, body: CommunityHelpIn, module: Module
) -> CommunityProposalOut:
    proposal = await module.proposals.set_help(principal, proposal_id, body.help_wanted, body.note)
    return await proposal_out(module, principal, proposal)


@router.post("/community/proposals/{proposal_id}/vote", response_model=CommunityVoteOut)
async def vote(principal: Reader, proposal_id: UUID, module: Module) -> CommunityVoteOut:
    """Active-account invariant: any active account, free, no minimum level."""
    return CommunityVoteOut(votes=await module.votes.cast(principal, proposal_id), my_vote=True)


@router.delete("/community/proposals/{proposal_id}/vote", response_model=CommunityVoteOut)
async def retract_vote(principal: Reader, proposal_id: UUID, module: Module) -> CommunityVoteOut:
    return CommunityVoteOut(votes=await module.votes.retract(principal, proposal_id), my_vote=False)


@router.get(
    "/community/proposals/{proposal_id}/participations", response_model=list[CommunityParticipationOut]
)
async def participations(
    principal: Reader, proposal_id: UUID, module: Module
) -> list[CommunityParticipationOut]:
    await module.proposals.get(principal, proposal_id)
    me = user_of(principal)
    out: list[CommunityParticipationOut] = []
    for row in await module.participations.of_proposal(proposal_id):
        member = None
        if row.user_id == me or await shown(module.visibility, principal, row.user_id, PROJECTS, True):
            member = CommunityPersonOut(id=row.user_id, display_name=await module.display_name(row.user_id))
        out.append(
            CommunityParticipationOut(
                id=row.id,
                role=row.role,
                note=row.note,
                member=member,
                mine=row.user_id == me,
                recognized=row.recognized_at is not None,
            )
        )
    return out


@router.post(
    "/community/proposals/{proposal_id}/participation",
    response_model=CommunityParticipationOut,
    status_code=201,
)
async def participate(
    principal: Participant, proposal_id: UUID, body: CommunityParticipateIn, module: Module
) -> CommunityParticipationOut:
    row = await module.participations.join(principal, proposal_id, body.role, body.note)
    return CommunityParticipationOut(
        id=row.id, role=row.role, note=row.note, member=None, mine=True, recognized=False
    )


@router.delete("/community/proposals/{proposal_id}/participation", status_code=204)
async def leave(principal: Participant, proposal_id: UUID, module: Module) -> Response:
    await module.participations.leave(principal, proposal_id)
    return Response(status_code=204)


@router.post(
    "/community/proposals/{proposal_id}/participations/{participation_id}/recognize",
    response_model=CommunityParticipationOut,
)
async def recognize(
    principal: Participant, proposal_id: UUID, participation_id: UUID, module: Module
) -> CommunityParticipationOut:
    row = await module.participations.recognize(principal, proposal_id, participation_id)
    return CommunityParticipationOut(
        id=row.id, role=row.role, note=row.note, member=None, mine=False, recognized=True
    )


# --- moderation ------------------------------------------------------------------------------------------
@router.get("/admin/community/moderation", response_model=list[CommunityProposalOut])
async def moderation_queue(principal: Moderator, module: Module) -> list[CommunityProposalOut]:
    return [await proposal_out(module, principal, p) for p in await module.proposals.queue()]


@router.post(
    "/admin/community/moderation/proposals/{proposal_id}/approve", response_model=CommunityProposalOut
)
async def approve(
    principal: Moderator, proposal_id: UUID, body: CommunityModerationIn, module: Module
) -> CommunityProposalOut:
    proposal = await module.proposals.moderate(principal, proposal_id, "approved", body.reason)
    return await proposal_out(module, principal, proposal)


@router.post(
    "/admin/community/moderation/proposals/{proposal_id}/reject", response_model=CommunityProposalOut
)
async def reject(
    principal: Moderator, proposal_id: UUID, body: CommunityModerationIn, module: Module
) -> CommunityProposalOut:
    proposal = await module.proposals.moderate(principal, proposal_id, "rejected", body.reason)
    return await proposal_out(module, principal, proposal)
