"""Projects (T009; R2, R5): the lifecycle record of each Community proposal and its permissioned,
audited transitions. Every change appends to the history (append-only), emits ``project.status_changed``
(dedup ``(project, seq)``) and applies the funding rules (resolution) in the same transaction. Opening a
project freezes its funding rules. Validation is a gate the Admin decides — informed by votes and funding,
never bound to them. This service is also the ``ProjectLifecycle`` capability Community reads."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.marketplace import FundingSummary, ProjectRef, ProjectState
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.models import (
    Project,
    ProjectFunding,
    ProjectNote,
    ProjectsSeen,
    ProjectStateHistory,
)
from portalab.modules.marketplace.observability import metrics
from portalab.modules.marketplace.projects.rules import parse_rules
from portalab.modules.marketplace.projects.state import accepts_funding, accepts_votes, allowed
from portalab.modules.marketplace.resolution.service import Resolution

SYSTEM = Principal(channel="system")


class ProjectNotFound(NotFound):
    default_code = "project.not_found"
    default_title = "Project not found"


class InvalidTransition(Conflict):
    default_code = "project.invalid_transition"
    default_title = "This change is not allowed in the project's state"


def _actor_id(actor: Principal) -> UUID | None:
    return actor.acting_for or actor.user_id


class Projects:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        resolution: Resolution,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.resolution = resolution
        self.clock = clock

    # --- ProjectLifecycle (012) ----------------------------------------------------------------------
    async def register(self, proposal_ref: str, proposer: UUID | None, title: str) -> ProjectRef:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            created = await uow.session.scalar(
                insert(Project)
                .values(
                    proposal_ref=proposal_ref,
                    proposer_id=proposer,
                    title=title[:200],
                    state="idea",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=[Project.proposal_ref])
                .returning(Project.id)
            )
            project = await uow.session.scalar(select(Project).where(Project.proposal_ref == proposal_ref))
            assert project is not None
            if created is not None:
                await self._history(uow.session, project, None, "idea", SYSTEM, None, now)
                metrics.increment("marketplace.projects.registered")
        return ProjectRef(project.id, project.state)  # type: ignore[arg-type]

    async def _by_ref(self, session: AsyncSession, ref: str) -> Project | None:
        try:
            as_id = UUID(ref)
        except ValueError:
            as_id = None
        project = await session.scalar(select(Project).where(Project.proposal_ref == ref))
        if project is None and as_id is not None:
            project = await session.get(Project, as_id)
        return project

    async def state(self, project_ref: str) -> ProjectState | None:
        async with self.database.session() as session:
            project = await self._by_ref(session, project_ref)
        return project.state if project else None  # type: ignore[return-value]

    async def accepts_votes(self, project_ref: str) -> bool:
        current = await self.state(project_ref)
        return current is not None and accepts_votes(current)

    async def funding_summary(self, project_ref: str) -> FundingSummary | None:
        async with self.database.session() as session:
            project = await self._by_ref(session, project_ref)
            if project is None:
                return None
            totals = await self.totals(session, project.id)
        return FundingSummary(
            project.state,  # type: ignore[arg-type]
            accepts_funding(project.state),
            totals["reserved"],
            totals["consumed"],
            totals["funders"],
            project.goal_amount,
        )

    async def totals(self, session: AsyncSession, project_id: UUID) -> dict[str, int]:
        rows = (
            await session.execute(
                select(ProjectFunding.tranches, ProjectFunding.user_id).where(
                    ProjectFunding.project_id == project_id,
                    ProjectFunding.status != "destroyed_on_deletion",
                )
            )
        ).all()
        reserved = sum(
            int(t["amount"]) for tranches, _ in rows for t in tranches if t["status"] == "reserved"
        )
        consumed = sum(
            int(t["amount"]) for tranches, _ in rows for t in tranches if t["status"] == "consumed"
        )
        funders = len(
            {
                user
                for tranches, user in rows
                if any(t["status"] in ("reserved", "consumed") for t in tranches)
            }
        )
        return {"reserved": reserved, "consumed": consumed, "funders": funders}

    # --- reads ---------------------------------------------------------------------------------------
    async def get(self, project_id: UUID) -> Project:
        async with self.database.session() as session:
            project = await session.get(Project, project_id)
        if project is None:
            raise ProjectNotFound("This project does not exist.")
        return project

    async def all(self, state: str | None = None, limit: int = 100) -> list[Project]:
        statement = (
            select(Project).order_by(Project.updated_at.desc(), Project.id).limit(max(1, min(limit, 200)))
        )
        if state:
            statement = statement.where(Project.state == state)
        async with self.database.session() as session:
            return list((await session.execute(statement)).scalars())

    async def history(self, project_id: UUID) -> list[ProjectStateHistory]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(ProjectStateHistory)
                        .where(ProjectStateHistory.project_id == project_id)
                        .order_by(ProjectStateHistory.seq)
                    )
                ).scalars()
            )

    async def notes(self, project_id: UUID) -> list[ProjectNote]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(ProjectNote)
                        .where(ProjectNote.project_id == project_id)
                        .order_by(ProjectNote.created_at)
                    )
                ).scalars()
            )

    # --- what is new to a member (#303) -----------------------------------------------------------------
    async def unseen(self, user: UUID) -> int:
        """The projects added or moved on since I last opened them (all of them, never opened) — an idea
        waits for its moderation, and my own project just proposed is no news to me."""
        seen = select(ProjectsSeen.seen_at).where(ProjectsSeen.user_id == user).scalar_subquery()
        async with self.database.session() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(Project)
                .where(
                    Project.state != "idea",
                    or_(seen.is_(None), Project.updated_at > seen),
                    not_(and_(Project.proposer_id == user, Project.state == "proposal")),
                )
            )
        return int(count or 0)

    async def mark_seen(self, user: UUID) -> datetime | None:
        """I opened the projects: nothing is new any more. Returns when I had last looked before."""
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            before = await uow.session.scalar(
                select(ProjectsSeen.seen_at).where(ProjectsSeen.user_id == user)
            )
            await uow.session.execute(
                insert(ProjectsSeen)
                .values(user_id=user, seen_at=now)
                .on_conflict_do_update(index_elements=[ProjectsSeen.user_id], set_={"seen_at": now})
            )
        return before

    # --- transitions ---------------------------------------------------------------------------------
    async def _history(
        self,
        session: AsyncSession,
        project: Project,
        source: str | None,
        target: str,
        actor: Principal,
        reason: str | None,
        at: datetime,
    ) -> int:
        seq = (
            int(
                await session.scalar(
                    select(func.coalesce(func.max(ProjectStateHistory.seq), 0)).where(
                        ProjectStateHistory.project_id == project.id
                    )
                )
                or 0
            )
            + 1
        )
        session.add(
            ProjectStateHistory(
                project_id=project.id,
                seq=seq,
                from_state=source,
                to_state=target,
                actor_user_id=_actor_id(actor),
                reason=reason,
                created_at=at,
            )
        )
        await session.flush()
        await self.events.publish(
            session,
            "project.status_changed",
            {
                "project": str(project.id),
                "proposal": project.proposal_ref,
                "from_state": source,
                "to_state": target,
                "seq": seq,
            },
            occurred_at=at,
            actor=actor,
            subject=SubjectRef("project", str(project.id)),
            dedup_key=f"project.status_changed:{project.id}:{seq}",
        )
        return seq

    async def transition(
        self,
        actor: Principal,
        project_id: UUID,
        target: str,
        *,
        reason: str | None = None,
        note: str | None = None,
        expected_version: int | None = None,
        rules: dict[str, Any] | None = None,
    ) -> Project:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            project = await session.get(Project, project_id, with_for_update=True)
            if project is None:
                raise ProjectNotFound("This project does not exist.")
            if expected_version is not None and expected_version != project.version:
                raise Conflict("The project changed meanwhile; reload it.", code="project.version_conflict")
            source = project.state
            if not allowed(source, target):
                raise InvalidTransition(
                    f"A project cannot go from {source} to {target}.",
                    extensions={"from": source, "to": target},
                )
            if target == "open":
                if project.rules_frozen_at is not None:
                    raise Conflict("The funding rules are frozen.", code="project.rules_frozen")
                frozen = parse_rules(rules or {})
                project.funding_rules = frozen.model_dump(mode="json")
                project.goal_amount = frozen.goal_amount
                project.rules_frozen_at = now
            elif rules is not None:
                raise ValidationFailed(
                    "Funding rules are set when the project opens.", code="project.rules_frozen"
                )
            if target == "development" and source == "validation":
                project.validated_by, project.validated_at = _actor_id(actor), now
            project.state, project.version, project.updated_at = target, project.version + 1, now
            seq = await self._history(session, project, source, target, actor, reason, now)
            if note:
                session.add(
                    ProjectNote(
                        project_id=project.id,
                        author_id=_actor_id(actor),
                        state=target,
                        public_note=note[:4000],
                        created_at=now,
                    )
                )
            settled = await self.resolution.settle(session, project, actor)
            await self.audit.record(
                session,
                AuditRecord(
                    action="project.transitioned",
                    actor=actor,
                    resource=ResourceRef("project", str(project.id)),
                    decision="allow",
                    context={"from": source, "to": target, "seq": seq, "settled": settled},
                    sensitive=True,
                ),
            )
        metrics.increment(f"marketplace.projects.to_{target}")
        return project
