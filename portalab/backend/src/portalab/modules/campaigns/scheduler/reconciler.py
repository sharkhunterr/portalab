"""Schedule reconciliation (T011; R3, R4): every ``campaigns.reconcileSeconds`` the desired state of each
campaign is computed — an unexpired manual override wins, otherwise the occurrence containing *now* — and
intervals are opened/closed accordingly. A boundary caught within tolerance is logged at its exact
scheduled instant; after downtime the actual repair time is logged (an interval never claims time it was
not open). ``campaign.ending_soon`` is emitted once per occurrence; overrides expire automatically."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.campaigns.definitions.schema import CampaignDefinition
from portalab.modules.campaigns.intervals.manager import Intervals
from portalab.modules.campaigns.models import Campaign, CampaignVersion, Occurrence, OpenInterval, Override
from portalab.modules.campaigns.observability import metrics

LIVE = ("scheduled", "active", "paused")


async def active_override(session: AsyncSession, campaign: Campaign, now: datetime) -> Override | None:
    return (
        await session.execute(
            select(Override)
            .where(
                Override.campaign_id == campaign.id,
                Override.expired_at.is_(None),
                Override.from_at <= now,
                or_(Override.until_at.is_(None), Override.until_at > now),
            )
            .order_by(Override.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def occurrence_at(session: AsyncSession, campaign: Campaign, now: datetime) -> Occurrence | None:
    return (
        await session.execute(
            select(Occurrence)
            .where(
                Occurrence.campaign_id == campaign.id,
                Occurrence.status.in_(("planned", "active")),
                Occurrence.start_at <= now,
                Occurrence.end_at > now,
            )
            .order_by(Occurrence.start_at)
            .limit(1)
        )
    ).scalar_one_or_none()


class Reconciler:
    def __init__(
        self, database: Database, intervals: Intervals, config: Any, *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.intervals = intervals
        self.config = config  # callable → CampaignsConfig
        self.clock = clock

    def tolerance(self) -> timedelta:
        return timedelta(seconds=max(60, 2 * int(self.config().reconcile_seconds)))

    async def run(self, now: datetime | None = None) -> int:
        now = now or utc_now(self.clock)
        async with self.database.session() as session:
            ids = list((await session.execute(select(Campaign.id).where(Campaign.state.in_(LIVE)))).scalars())
        changed = 0
        for campaign_id in ids:
            async with self.database.unit_of_work() as uow:
                campaign = await uow.session.get(Campaign, campaign_id, with_for_update=True)
                if campaign is not None and campaign.state in LIVE:
                    changed += await self.reconcile(uow.session, campaign, now)
        return changed

    async def reconcile(self, session: AsyncSession, campaign: Campaign, now: datetime) -> int:
        await self._expire_overrides(session, campaign, now)
        override = await active_override(session, campaign, now)
        occurrence = await occurrence_at(session, campaign, now)
        desired = override.kind == "activate" if override is not None else occurrence is not None
        open_row = await session.get(OpenInterval, campaign.id)
        changed = 0
        if desired and open_row is None:
            manual = override is not None
            start = now
            if not manual and occurrence is not None and now - occurrence.start_at <= self.tolerance():
                start = occurrence.start_at
            elif not manual:
                metrics.increment("campaigns.boundary_late")
            was_paused = campaign.state == "paused"
            await self.intervals.open(
                session,
                campaign,
                start,
                cause="manual" if manual else "schedule",
                occurrence=occurrence.id if occurrence else None,
                actor=override.actor_user_id if override else None,
                reason=override.reason if override else None,
            )
            if occurrence is not None:
                occurrence.status = "active"
            if was_paused:
                await self.intervals.emit(
                    session,
                    "campaign.resumed",
                    campaign,
                    campaign.current_version,
                    now,
                    dedup=f"resumed:{now.isoformat()}",
                )
            changed += 1
        elif not desired and open_row is not None:
            closed_at = now
            if open_row.cause == "schedule" and open_row.occurrence_id is not None and override is None:
                ended = await session.get(Occurrence, open_row.occurrence_id)
                if ended is not None and ended.end_at <= now:
                    closed_at = ended.end_at
            await self.intervals.close(session, campaign, closed_at)
            if override is not None and occurrence is not None:
                campaign.state = "paused"
                await self.intervals.emit(
                    session,
                    "campaign.paused",
                    campaign,
                    campaign.current_version,
                    now,
                    occurrence.id,
                    "manual",
                )
            changed += 1
        await self._finish_occurrences(session, campaign, now)
        if desired:
            await self._ending_soon(session, campaign, override, occurrence, now)
        else:
            campaign.state = await self._resting_state(
                session, campaign, now, paused=campaign.state == "paused" and occurrence is not None
            )
        return changed

    async def _expire_overrides(self, session: AsyncSession, campaign: Campaign, now: datetime) -> None:
        rows = (
            await session.execute(
                select(Override).where(
                    Override.campaign_id == campaign.id,
                    Override.expired_at.is_(None),
                    and_(Override.until_at.is_not(None), Override.until_at <= now),
                )
            )
        ).scalars()
        for row in rows:
            row.expired_at = row.until_at

    async def _finish_occurrences(self, session: AsyncSession, campaign: Campaign, now: datetime) -> None:
        rows = (
            await session.execute(
                select(Occurrence).where(
                    Occurrence.campaign_id == campaign.id,
                    Occurrence.status.in_(("planned", "active")),
                    Occurrence.end_at <= now,
                )
            )
        ).scalars()
        for row in rows:
            row.status = "ended" if row.status == "active" else "skipped"

    async def _ending_soon(
        self,
        session: AsyncSession,
        campaign: Campaign,
        override: Override | None,
        occurrence: Occurrence | None,
        now: datetime,
    ) -> None:
        end = override.until_at if override is not None else (occurrence.end_at if occurrence else None)
        if end is None:
            return
        version = await session.get(CampaignVersion, (campaign.id, campaign.current_version))
        hours = None
        if version is not None:
            hours = CampaignDefinition.model_validate(version.definition).ending_soon_hours
        window = timedelta(hours=hours or int(self.config().ending_soon_hours))
        if end - now <= window:
            await self.intervals.emit(
                session,
                "campaign.ending_soon",
                campaign,
                campaign.current_version,
                now,
                occurrence.id if occurrence else None,
                dedup=f"soon:{occurrence.id if occurrence else end.isoformat()}",
            )

    async def _resting_state(
        self, session: AsyncSession, campaign: Campaign, now: datetime, *, paused: bool
    ) -> str:
        if paused:
            return "paused"
        upcoming = await session.scalar(
            select(Occurrence.id)
            .where(
                Occurrence.campaign_id == campaign.id, Occurrence.status == "planned", Occurrence.end_at > now
            )
            .limit(1)
        )
        pending = await session.scalar(
            select(Override.id)
            .where(Override.campaign_id == campaign.id, Override.expired_at.is_(None), Override.from_at > now)
            .limit(1)
        )
        return "scheduled" if upcoming is not None or pending is not None else "ended"
