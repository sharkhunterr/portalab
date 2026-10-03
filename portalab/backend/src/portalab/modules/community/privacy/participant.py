"""Privacy participant (T003, T027; 020/021): export lists the member's own feed entries, visibility
choices, proposals, votes and participations; final deletion removes feed entries, preferences and votes
(counts decremented), withdraws participations, and detaches the member from the proposals they made and
the events they organized (the content stays — it belongs to the community)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select, update

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.community.models import (
    CommunityEvent,
    FeedEntry,
    Participation,
    Proposal,
    VisibilityPreference,
    Vote,
    VoteCount,
)


class CommunityParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            entries = list(
                (
                    await session.execute(
                        select(FeedEntry)
                        .where(FeedEntry.actor_user_id == user_id)
                        .order_by(FeedEntry.occurred_at)
                    )
                ).scalars()
            )
            preferences = list(
                (
                    await session.execute(
                        select(VisibilityPreference).where(VisibilityPreference.user_id == user_id)
                    )
                ).scalars()
            )
        records = [
            ExportRecord(
                "community.feed_entry",
                {"kind": e.kind, "params": dict(e.params), "occurred_at": e.occurred_at.isoformat()},
            )
            for e in entries
        ]
        records += [
            ExportRecord("community.visibility", {"datum_class": p.datum_class, "level": p.level})
            for p in preferences
        ]
        async with self.database.session() as session:
            proposals = list(
                (await session.execute(select(Proposal).where(Proposal.proposer_id == user_id))).scalars()
            )
            votes = list((await session.execute(select(Vote).where(Vote.user_id == user_id))).scalars())
            participations = list(
                (
                    await session.execute(select(Participation).where(Participation.user_id == user_id))
                ).scalars()
            )
        records += [
            ExportRecord("community.proposal", {"title": p.title, "status": p.status, "kind": p.kind})
            for p in proposals
        ]
        records += [
            ExportRecord(
                "community.vote",
                {
                    "proposal": str(v.proposal_id),
                    "cast_at": v.cast_at.isoformat(),
                    "retracted": v.retracted_at is not None,
                },
            )
            for v in votes
        ]
        records += [
            ExportRecord(
                "community.participation",
                {"proposal": str(p.proposal_id), "role": p.role, "status": p.status},
            )
            for p in participations
        ]
        return records

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(delete(FeedEntry).where(FeedEntry.actor_user_id == user_id))
            await uow.session.execute(
                delete(VisibilityPreference).where(VisibilityPreference.user_id == user_id)
            )
            await uow.session.execute(
                update(CommunityEvent).where(CommunityEvent.organizer_id == user_id).values(organizer_id=None)
            )
            active = (
                await uow.session.execute(
                    select(Vote.proposal_id, func.count())
                    .where(Vote.user_id == user_id, Vote.retracted_at.is_(None))
                    .group_by(Vote.proposal_id)
                )
            ).all()
            for proposal_id, n in active:
                await uow.session.execute(
                    update(VoteCount)
                    .where(VoteCount.proposal_id == proposal_id)
                    .values(count=func.greatest(VoteCount.count - n, 0))
                )
            await uow.session.execute(delete(Vote).where(Vote.user_id == user_id))
            await uow.session.execute(
                update(Participation)
                .where(Participation.user_id == user_id)
                .values(status="withdrawn", note=None)
            )
            await uow.session.execute(
                update(Proposal).where(Proposal.proposer_id == user_id).values(proposer_id=None)
            )
