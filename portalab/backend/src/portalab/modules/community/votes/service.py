"""Votes (T023; R8, CD-007): one free up-vote of support per **active account** per proposal — an
invariant, not a configurable permission — with no minimum level. A vote can be retracted and re-cast
while the proposal is open and its lifecycle accepts votes. The public count is a transactional counter;
who voted stays private (the voter sees their own vote). Voting never implies funding and funding is
never a vote."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.community.models import Proposal, Vote, VoteCount
from portalab.modules.community.observability import metrics
from portalab.modules.community.proposals.service import (
    NotActiveAccount,
    ProposalNotFound,
    Proposals,
    user_of,
)


class VotingClosed(Conflict):
    default_code = "community.voting_closed"
    default_title = "This proposal does not accept votes"


class Votes:
    def __init__(
        self, database: Database, events: EventPublisher, proposals: Proposals, *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.events = events
        self.proposals = proposals
        self.clock = clock

    async def _open(self, proposal_id: UUID) -> Proposal:
        async with self.database.session() as session:
            proposal = await session.get(Proposal, proposal_id)
        if proposal is None or proposal.status not in ("open", "pending_moderation"):
            raise ProposalNotFound("This proposal does not exist.")
        if proposal.status != "open":
            raise VotingClosed("This proposal is not open for votes yet.")
        if proposal.kind == "project":
            lifecycle = self.proposals.lifecycle()
            if (
                proposal.lifecycle_ref is not None
                and lifecycle is not None
                and not await lifecycle.accepts_votes(str(proposal.id))
            ):
                raise VotingClosed("Voting is closed for this project.")
        return proposal

    async def _voter(self, actor: Principal) -> UUID:
        user = user_of(actor)
        if user is None or not await self.proposals.active(user):
            raise NotActiveAccount("Only active accounts can vote.")
        return user

    async def cast(self, actor: Principal, proposal_id: UUID) -> int:
        user = await self._voter(actor)
        proposal = await self._open(proposal_id)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            inserted = await session.scalar(
                insert(Vote)
                .values(proposal_id=proposal.id, user_id=user, cast_at=now)
                .on_conflict_do_nothing(
                    index_elements=[Vote.proposal_id, Vote.user_id], index_where=Vote.retracted_at.is_(None)
                )
                .returning(Vote.id)
            )
            if inserted is None:
                return await self._count(session, proposal.id)
            count = await session.scalar(
                update(VoteCount)
                .where(VoteCount.proposal_id == proposal.id)
                .values(count=VoteCount.count + 1)
                .returning(VoteCount.count)
            )
            seq = await session.scalar(
                select(func.count())
                .select_from(Vote)
                .where(Vote.proposal_id == proposal.id, Vote.user_id == user)
            )
            await self.events.publish(
                session,
                "project.vote_added",
                {"proposal": str(proposal.id), "count": int(count or 0)},
                occurred_at=now,
                actor=Principal(user_id=user, channel="system"),
                subject=SubjectRef("user", str(user)),
                dedup_key=f"project.vote_added:{proposal.id}:{user}:{seq}",
            )
        metrics.increment("community.votes.cast")
        return int(count or 0)

    async def retract(self, actor: Principal, proposal_id: UUID) -> int:
        user = await self._voter(actor)
        proposal = await self._open(proposal_id)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            retracted = await session.scalar(
                update(Vote)
                .where(Vote.proposal_id == proposal.id, Vote.user_id == user, Vote.retracted_at.is_(None))
                .values(retracted_at=now)
                .returning(Vote.id)
            )
            if retracted is None:
                return await self._count(session, proposal.id)
            count = await session.scalar(
                update(VoteCount)
                .where(VoteCount.proposal_id == proposal.id)
                .values(count=VoteCount.count - 1)
                .returning(VoteCount.count)
            )
            await self.events.publish(
                session,
                "project.vote_retracted",
                {"proposal": str(proposal.id), "count": int(count or 0)},
                occurred_at=now,
                actor=Principal(user_id=user, channel="system"),
                subject=SubjectRef("user", str(user)),
                dedup_key=f"project.vote_retracted:{retracted}",
            )
        return int(count or 0)

    async def _count(self, session: AsyncSession, proposal_id: UUID) -> int:
        row = await session.get(VoteCount, proposal_id)
        return int(row.count) if row else 0

    async def voted(self, user: UUID | None, proposal_ids: list[UUID]) -> set[UUID]:
        if user is None or not proposal_ids:
            return set()
        async with self.database.session() as session:
            rows = await session.execute(
                select(Vote.proposal_id).where(
                    Vote.user_id == user, Vote.proposal_id.in_(proposal_ids), Vote.retracted_at.is_(None)
                )
            )
            return set(rows.scalars())

    async def counts(self, proposal_ids: list[UUID]) -> dict[UUID, int]:
        if not proposal_ids:
            return {}
        async with self.database.session() as session:
            rows = await session.execute(
                select(VoteCount.proposal_id, VoteCount.count).where(VoteCount.proposal_id.in_(proposal_ids))
            )
            return {p: int(c) for p, c in rows.all()}
