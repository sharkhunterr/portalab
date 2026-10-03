"""Participation and recognition (T026; R10): members take part in an open project as contributor, tester
or helper. The proposer or a moderator may **recognize** a participation once — never their own — within
limits (``community.recognition.maxPerDay`` per recognizer, one per recognizer→recipient pair per
``pairCooldownDays``); it emits ``community.contribution_recognized`` (dedup participation) which a 013 reward
rule turns into Contribution for the recognized member. No messaging, following or chat is involved."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.community.models import Participation, Proposal, RecognitionLog
from portalab.modules.community.observability import metrics
from portalab.modules.community.proposals.service import (
    NotActiveAccount,
    ProposalNotFound,
    Proposals,
    user_of,
)

Role = Literal["contributor", "tester", "helper"]


class RecognitionLimit(Conflict):
    default_code = "community.recognition_limit"
    default_title = "Recognition limit reached"


class SelfRecognition(Forbidden):
    default_code = "community.self_recognition"
    default_title = "You cannot recognize yourself"


class Participations:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        proposals: Proposals,
        config: Callable[[], Any],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.proposals = proposals
        self.config = config
        self.clock = clock

    async def join(self, actor: Principal, proposal_id: UUID, role: Role, note: str | None) -> Participation:
        user = user_of(actor)
        if user is None or not await self.proposals.active(user):
            raise NotActiveAccount("Only active accounts can take part.")
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            proposal = await session.get(Proposal, proposal_id)
            if proposal is None or proposal.status != "open":
                raise ProposalNotFound("This proposal does not exist.")
            row = await session.scalar(
                select(Participation)
                .where(
                    Participation.proposal_id == proposal_id,
                    Participation.user_id == user,
                    Participation.role == role,
                )
                .with_for_update()
            )
            if row is not None and row.status == "active":
                return row
            if row is None:
                row = Participation(
                    proposal_id=proposal_id,
                    user_id=user,
                    role=role,
                    status="active",
                    note=None,
                    created_at=now,
                )
                session.add(row)
            row.status = "active"
            row.note = (note or "").strip()[:500] or None
            await session.flush()
            await self.events.publish(
                session,
                "project.participation_added",
                {"proposal": str(proposal_id), "participation": str(row.id), "role": role},
                occurred_at=now,
                actor=Principal(user_id=user, channel="system"),
                subject=SubjectRef("proposal", str(proposal_id)),
                dedup_key=f"project.participation_added:{row.id}:{now.isoformat()}",
            )
        return row

    async def leave(self, actor: Principal, proposal_id: UUID) -> int:
        user = user_of(actor)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            rows = list(
                (
                    await uow.session.execute(
                        select(Participation)
                        .where(
                            Participation.proposal_id == proposal_id,
                            Participation.user_id == user,
                            Participation.status == "active",
                        )
                        .with_for_update()
                    )
                ).scalars()
            )
            for row in rows:
                row.status = "withdrawn"
                await self.events.publish(
                    uow.session,
                    "project.participation_withdrawn",
                    {"proposal": str(proposal_id), "participation": str(row.id), "role": row.role},
                    occurred_at=now,
                    actor=actor,
                    subject=SubjectRef("proposal", str(proposal_id)),
                    dedup_key=f"project.participation_withdrawn:{row.id}:{now.isoformat()}",
                )
        return len(rows)

    async def of_proposal(self, proposal_id: UUID) -> list[Participation]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(Participation)
                        .where(Participation.proposal_id == proposal_id, Participation.status == "active")
                        .order_by(Participation.created_at, Participation.id)
                    )
                ).scalars()
            )

    async def recognize(self, actor: Principal, proposal_id: UUID, participation_id: UUID) -> Participation:
        recognizer = user_of(actor)
        if recognizer is None or not await self.proposals.active(recognizer):
            raise NotActiveAccount("Only active accounts can recognize contributions.")
        config = self.config()
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            row = await session.get(Participation, participation_id, with_for_update=True)
            proposal = await session.get(Proposal, proposal_id)
            if row is None or proposal is None or row.proposal_id != proposal.id or row.status != "active":
                raise NotFound("This participation does not exist.", code="community.participation_not_found")
            if proposal.proposer_id != recognizer and not await self.proposals.is_moderator(actor):
                raise Forbidden(
                    "Only the proposer or a moderator can recognize.", code="community.not_proposer"
                )
            if row.user_id == recognizer:
                raise SelfRecognition("You cannot recognize your own participation.")
            if row.recognized_at is not None:
                raise Conflict(
                    "This participation is already recognized.", code="community.already_recognized"
                )
            today = int(
                await session.scalar(
                    select(func.count())
                    .select_from(RecognitionLog)
                    .where(
                        RecognitionLog.recognizer_id == recognizer,
                        RecognitionLog.created_at >= now - timedelta(days=1),
                    )
                )
                or 0
            )
            if today >= config.recognition_max_per_day:
                raise RecognitionLimit("You reached today's recognition limit.")
            pair = await session.scalar(
                select(RecognitionLog.id)
                .where(
                    RecognitionLog.recognizer_id == recognizer,
                    RecognitionLog.recipient_id == row.user_id,
                    RecognitionLog.created_at >= now - timedelta(days=config.recognition_pair_cooldown_days),
                )
                .limit(1)
            )
            if pair is not None:
                raise RecognitionLimit("You recently recognized this member.")
            row.recognized_at, row.recognized_by = now, recognizer
            session.add(
                RecognitionLog(
                    participation_id=row.id,
                    recognizer_id=recognizer,
                    recipient_id=row.user_id,
                    created_at=now,
                )
            )
            published = await self.events.publish(
                session,
                "community.contribution_recognized",
                {
                    "proposal": str(proposal.id),
                    "participation": str(row.id),
                    "role": row.role,
                    "recognizer": str(recognizer),
                },
                occurred_at=now,
                actor=Principal(user_id=row.user_id, channel="system"),  # the recognized member is credited
                subject=SubjectRef("user", str(row.user_id)),
                dedup_key=f"community.contribution_recognized:{row.id}",
            )
            await self.audit.record(
                session,
                AuditRecord(
                    action="community.contribution_recognized",
                    actor=actor,
                    resource=ResourceRef("participation", str(row.id), owner_id=row.user_id),
                    decision="allow",
                    context={"proposal": str(proposal.id), "role": row.role},
                    event_id=getattr(published, "event_id", None),
                ),
            )
        metrics.increment("community.recognitions")
        return row
