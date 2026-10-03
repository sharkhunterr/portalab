"""Activation intervals (T010; R2): the **authoritative history** of when a campaign was active. Opening
inserts the single ``open_intervals`` row; closing moves it into the append-only ``activation_log`` as a
closed ``[opened, closed)`` range (overlaps are rejected by the exclusion constraint) — in the caller's
transaction, together with the lifecycle event."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.authz_port import Principal
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.modules.campaigns.models import ActivationLog, Campaign, OpenInterval


class Intervals:
    def __init__(self, events: EventPublisher) -> None:
        self.events = events

    async def emit(
        self,
        session: AsyncSession,
        name: str,
        campaign: Campaign,
        version: int,
        at: datetime,
        occurrence: UUID | None = None,
        cause: str | None = None,
        actor: Principal | None = None,
        dedup: str | None = None,
    ) -> None:
        payload: dict[str, object] = {"campaign": campaign.key, "version": version}
        if occurrence is not None:
            payload["occurrence"] = str(occurrence)
        if cause is not None:
            payload["cause"] = cause
        await self.events.publish(
            session,
            name,
            payload,
            occurred_at=at,
            actor=actor or Principal(channel="system"),
            subject=SubjectRef("campaign", str(campaign.id)),
            dedup_key=f"{name}:{campaign.id}:{dedup or occurrence or at.isoformat()}",
        )

    async def open(
        self,
        session: AsyncSession,
        campaign: Campaign,
        at: datetime,
        *,
        cause: str,
        occurrence: UUID | None = None,
        actor: UUID | None = None,
        reason: str | None = None,
    ) -> OpenInterval | None:
        if await session.get(OpenInterval, campaign.id) is not None:
            return None
        row = OpenInterval(
            campaign_id=campaign.id,
            version=campaign.current_version,
            opened_at=at,
            cause=cause,
            actor_user_id=actor,
            occurrence_id=occurrence,
            reason=reason,
        )
        session.add(row)
        campaign.state = "active"
        await session.flush()
        await self.emit(
            session,
            "campaign.started",
            campaign,
            campaign.current_version,
            at,
            occurrence,
            cause,
            actor=Principal(user_id=actor) if actor else None,
            dedup=f"{occurrence or 'manual'}:{at.isoformat()}",
        )
        return row

    async def close(
        self,
        session: AsyncSession,
        campaign: Campaign,
        at: datetime,
        *,
        actor: UUID | None = None,
        reason: str | None = None,
    ) -> ActivationLog | None:
        row = await session.get(OpenInterval, campaign.id, with_for_update=True)
        if row is None:
            return None
        closed = max(at, row.opened_at)
        log = ActivationLog(
            campaign_id=campaign.id,
            version=row.version,
            occurrence_id=row.occurrence_id,
            during=Range(row.opened_at, closed, bounds="[)"),
            cause=row.cause,
            actor_user_id=row.actor_user_id,
            reason=row.reason or reason,
        )
        await session.execute(delete(OpenInterval).where(OpenInterval.campaign_id == campaign.id))
        if closed > row.opened_at:
            session.add(log)
        await session.flush()
        await self.emit(
            session,
            "campaign.ended",
            campaign,
            row.version,
            closed,
            row.occurrence_id,
            row.cause,
            actor=Principal(user_id=actor) if actor else None,
            dedup=f"{row.occurrence_id or 'manual'}:{row.opened_at.isoformat()}",
        )
        return log
