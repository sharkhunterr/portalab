"""Funding (T011; R3 to R5, FR-023/026): a member reserves Coins on an **open** project — a 013 ledger
reservation per consumption tranche, atomic with the funding row — after explicitly acknowledging that
funding does **not** guarantee implementation. Limits come from the frozen rules and the settings; the
balance never goes negative; requests are idempotent; voting is neither required nor implied."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, ValidationFailed
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.models import Project, ProjectFunding
from portalab.modules.marketplace.observability import metrics
from portalab.modules.marketplace.projects.rules import FundingRules, split
from portalab.modules.marketplace.projects.service import ProjectNotFound
from portalab.modules.marketplace.resolution.service import Resolution


class FundingClosed(Conflict):
    default_code = "project.funding_closed"
    default_title = "This project does not accept funding"


class Fundings:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        resolution: Resolution,
        config: Callable[[], Any],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.resolution = resolution
        self.config = config
        self.clock = clock

    async def _active(self, user: UUID) -> bool:
        providers = self.capabilities.system_providers(DIRECTORY)
        return bool(providers) and bool(await providers[0].provider.is_active_account(user))

    async def fund(
        self, actor: Principal, project_id: UUID, amount: int, *, acknowledged: bool, request_key: str
    ) -> ProjectFunding:
        user = actor.acting_for or actor.user_id
        if user is None or not await self._active(user):
            raise Forbidden("Only active accounts can fund projects.", code="project.not_active_account")
        if not acknowledged:
            raise ValidationFailed(
                "Acknowledge that funding does not guarantee the project will be built.",
                code="project.acknowledgement_required",
            )
        config = self.config()
        key = f"fund:{user}:{project_id}:{request_key}"[:200]
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            existing = await session.scalar(
                select(ProjectFunding).where(ProjectFunding.idempotency_key == key)
            )
            if existing is not None:
                return existing
            project = await session.get(Project, project_id, with_for_update=True)
            if project is None:
                raise ProjectNotFound("This project does not exist.")
            if project.state != "open" or project.funding_rules is None:
                raise FundingClosed("This project does not accept funding now.")
            rules = FundingRules.model_validate(project.funding_rules)
            low = max(rules.min_funding, config.funding_min_amount)
            high = min(rules.max_funding_per_user, config.funding_max_per_user)
            already = int(
                await session.scalar(
                    select(func.coalesce(func.sum(ProjectFunding.amount), 0)).where(
                        ProjectFunding.project_id == project.id,
                        ProjectFunding.user_id == user,
                        ProjectFunding.status.in_(("reserved", "partially_consumed")),
                    )
                )
                or 0
            )
            if amount < low or already + amount > high:
                raise ValidationFailed(
                    "This amount is outside the project's funding limits.",
                    code="project.funding_limits",
                    extensions={"min": low, "max": max(0, high - already)},
                )
            economy = self.resolution.economy()
            tranches = []
            for index, (consume_at, share) in enumerate(split(amount, rules)):
                reservation = await economy.reserve(
                    user,
                    share,
                    source_ref=f"project:{project.id}",
                    idempotency_key=f"{key}:{index}",
                    source_kind="community_funding",
                    session=session,
                )
                tranches.append(
                    {
                        "reservation": str(reservation.id),
                        "amount": share,
                        "consume_at": consume_at,
                        "status": "reserved",
                    }
                )
            funding = ProjectFunding(
                project_id=project.id,
                user_id=user,
                amount=amount,
                idempotency_key=key,
                tranches=tranches,
                status="reserved",
                acknowledged_at=now,
                created_at=now,
            )
            session.add(funding)
            await session.flush()
            await self.events.publish(
                session,
                "project.funding_added",
                {"project": str(project.id), "funding": str(funding.id), "amount": amount},
                occurred_at=now,
                actor=actor,
                subject=SubjectRef("user", str(user)),
                dedup_key=f"project.funding_added:{key}",
            )
        metrics.increment("marketplace.funding.added", amount)
        return funding

    async def mine(self, user: UUID) -> list[tuple[ProjectFunding, Project]]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(ProjectFunding, Project)
                    .join(Project, Project.id == ProjectFunding.project_id)
                    .where(ProjectFunding.user_id == user)
                    .order_by(ProjectFunding.created_at.desc(), ProjectFunding.id)
                )
            ).all()
        return [(f, p) for f, p in rows]

    async def of_project(self, project_id: UUID) -> list[ProjectFunding]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(ProjectFunding)
                        .where(ProjectFunding.project_id == project_id)
                        .order_by(ProjectFunding.created_at, ProjectFunding.id)
                    )
                ).scalars()
            )
