"""Onboarding progress tracker (T029). Identity only tracks steps; each step's content belongs to its module
(profile → identity, notifications → 010, privacy → 021, dashboard → 004, discovery → 023…)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.models import ONBOARDING_STEPS, OnboardingProgress
from portalab.modules.identity.services.common import publish
from portalab.modules.identity.settings import ONBOARDING_ENABLED, ONBOARDING_MESSAGE

#: #7 — the guided tours of the portal (the first steps each have one); others are refused.
TOURS = frozenset({"portal", "profile", "dashboard", "request", "request_status", "shop", "ticket", "stats"})


@dataclass(frozen=True, slots=True)
class StepProgress:
    step: str
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class Welcome:
    """027: what the welcome shows — whether it is on, and the administrator's message."""

    enabled: bool
    message: str


class OnboardingService:
    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def welcome(self) -> Welcome:
        try:
            providers = self.ctx.capabilities.system_providers(CONFIG)
            reader = providers[0].provider if providers else None
        except Exception:
            reader = None
        values: dict[str, object] = {ONBOARDING_ENABLED: True, ONBOARDING_MESSAGE: ""}
        for key in values:
            try:
                if reader is not None:
                    values[key] = (await reader.get(key)).value
            except Exception:  # noqa: S112 — the default stands
                continue
        return Welcome(
            enabled=values[ONBOARDING_ENABLED] is not False,
            message=str(values[ONBOARDING_MESSAGE] or "")[:2000],
        )

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

    async def tour_completed(self, principal: Principal, tour: str) -> None:
        """#7: a guided tour seen to its end — said once per member and tour (the missions listen to it)."""
        if principal.user_id is None or tour not in TOURS:
            raise NotFound()
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            await publish(
                self.ctx,
                uow.session,
                "user.tour_completed",
                principal.user_id,
                actor=principal,
                occurred_at=now,
                metadata={"tour": tour},
                dedup_key=f"user:{principal.user_id}:tour:{tour}",
            )

    async def complete(self, principal: Principal, step: str) -> list[StepProgress]:
        if principal.user_id is None or step not in ONBOARDING_STEPS:
            raise NotFound()
        user_id = principal.user_id
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            row = await uow.session.get(OnboardingProgress, (user_id, step), with_for_update=True)
            if row is None:  # 027: a step added after the member's onboarding started (the tour)
                row = OnboardingProgress(user_id=user_id, step=step, started_at=now, completed_at=None)
                uow.session.add(row)
            if row.completed_at is None:
                row.completed_at = now
                await uow.session.flush()
                await publish(
                    self.ctx,
                    uow.session,
                    "user.onboarding_step_completed",
                    user_id,
                    actor=principal,
                    occurred_at=now,
                    metadata={"step": step},
                    dedup_key=f"user:{user_id}:onboarding:{step}",
                )
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
