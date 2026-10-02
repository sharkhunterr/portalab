"""Onboarding progress tracker (T029). Identity only tracks steps; each step's content belongs to its module
(profile → identity, notifications → 010, privacy → 021, dashboard → 004, discovery → 023…)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.models import ONBOARDING_STEPS, OnboardingProgress
from portalab.modules.identity.services.common import publish


@dataclass(frozen=True, slots=True)
class StepProgress:
    step: str
    completed_at: datetime | None


class OnboardingService:
    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def start(self, session: AsyncSession, user_id: UUID, now: datetime) -> None:
        for step in ONBOARDING_STEPS:
            await session.execute(
                insert(OnboardingProgress)
                .values(user_id=user_id, step=step, started_at=now, completed_at=None)
                .on_conflict_do_nothing(index_elements=["user_id", "step"])
            )

    async def progress(self, session: AsyncSession, user_id: UUID) -> list[StepProgress]:
        rows = (
            await session.execute(select(OnboardingProgress).where(OnboardingProgress.user_id == user_id))
        ).scalars()
        by_step = {row.step: row.completed_at for row in rows}
        return [StepProgress(step, by_step[step]) for step in ONBOARDING_STEPS if step in by_step]

    async def complete(self, principal: Principal, step: str) -> list[StepProgress]:
        if principal.user_id is None or step not in ONBOARDING_STEPS:
            raise NotFound()
        user_id = principal.user_id
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            row = await uow.session.get(OnboardingProgress, (user_id, step), with_for_update=True)
            if row is None:
                raise NotFound("Onboarding has not started for this account.")
            if row.completed_at is None:
                row.completed_at = now
                await uow.session.flush()
                progress = await self.progress(uow.session, user_id)
                if all(item.completed_at is not None for item in progress):
                    await publish(
                        self.ctx,
                        uow.session,
                        "user.onboarding_completed",
                        user_id,
                        actor=principal,
                        occurred_at=now,
                        dedup_key=f"user:{user_id}:onboarding_completed",
                    )
            return await self.progress(uow.session, user_id)
