"""Lifecycle display and notifications (T024; R7, R9): Community reads a project's state and public funding
summary from Marketplace (``ProjectLifecycle``, 015) — never stores them — and, when 015 reports
``project.status_changed``, notifies the proposer, current voters and active participants through 010
(``community.project``, coalesced per project). Funding itself happens in Marketplace's flow."""

from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.modules.community.models import Participation, Proposal, Vote
from portalab.modules.community.observability import log
from portalab.modules.community.proposals.service import Proposals

CONSUMER = "community.project_status"
OWNER = "module:community"
CATEGORY = "community.project"


async def lifecycle_summary(proposals: Proposals, proposal: Proposal) -> dict[str, Any]:
    if proposal.kind != "project":
        return {"state": "none"}
    lifecycle = proposals.lifecycle()
    if lifecycle is None or proposal.lifecycle_ref is None:
        return {"state": "unavailable"}
    try:
        summary = await lifecycle.funding_summary(str(proposal.id))
    except Exception:
        return {"state": "unavailable"}
    if summary is None:
        return {"state": "unavailable"}
    return {
        "state": summary.state,
        "project_id": proposal.lifecycle_ref,
        "accepts_funding": summary.accepts_funding,
        "reserved": summary.reserved,
        "consumed": summary.consumed,
        "funders": summary.funders,
        "goal_amount": summary.goal_amount,
    }


class StatusNotifier:
    def __init__(self, database: Database, capabilities: CapabilityRegistry) -> None:
        self.database = database
        self.capabilities = capabilities

    def consumer(self) -> Consumer:
        return Consumer(CONSUMER, frozenset({"project.status_changed"}), self.handle, OWNER)

    async def handle(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        if ctx.replay:
            return
        try:
            proposal_id = UUID(str(envelope.payload.get("proposal")))
        except ValueError:
            return
        async with self.database.session() as session:
            proposal = await session.get(Proposal, proposal_id)
            if proposal is None:
                return
            voters = (
                await session.execute(
                    select(Vote.user_id).where(Vote.proposal_id == proposal.id, Vote.retracted_at.is_(None))
                )
            ).scalars()
            participants = (
                await session.execute(
                    select(Participation.user_id).where(
                        Participation.proposal_id == proposal.id, Participation.status == "active"
                    )
                )
            ).scalars()
            recipients = list(dict.fromkeys([u for u in (proposal.proposer_id, *voters, *participants) if u]))
        if not recipients:
            return
        providers = self.capabilities.system_providers(NOTIFY)
        if not providers:
            return
        state = str(envelope.payload.get("to_state"))
        try:
            await providers[0].provider.send(
                CommunicationRequest(
                    category=CATEGORY,
                    template_key=f"community:notify.project.{state}",
                    audience=Users(tuple(recipients)),
                    dedup_key=f"project:{proposal.id}:{envelope.payload.get('seq')}",
                    params={"proposal": proposal.title[:120], "state": state},
                    subject_ref=f"proposal:{proposal.id}",
                    action_url=f"/community/proposals/{proposal.id}",
                )
            )
        except Exception:
            log.warning("project status notification not sent")
