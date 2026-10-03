"""Manual activation / deactivation (T013; R4): an override is recorded with actor, reason and its validity;
it wins over the schedule — *activate* until the end of the current occurrence (or ``until``), *deactivate*
until the next scheduled start (or ``until``) — then the schedule resumes automatically. An override of the
same kind already in force is a conflict; an opposite one replaces it. Applied at once, audited."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.campaigns.definitions.service import CampaignNotFound, actor_id
from portalab.modules.campaigns.models import Campaign, Occurrence, Override
from portalab.modules.campaigns.observability import metrics
from portalab.modules.campaigns.scheduler.reconciler import Reconciler, active_override, occurrence_at


class OverrideConflict(Conflict):
    default_code = "campaign.override_conflict"
    default_title = "Conflicting override"


class Overrides:
    def __init__(
        self, database: Database, audit: AuditSink, reconciler: Reconciler, *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.audit = audit
        self.reconciler = reconciler
        self.clock = clock

    async def apply(
        self,
        actor: Principal,
        campaign_id: UUID,
        kind: Literal["activate", "deactivate"],
        reason: str,
        until: datetime | None = None,
    ) -> Override:
        now = utc_now(self.clock)
        if until is not None and until <= now:
            raise ValidationFailed("'until' must be in the future.", code="campaign.override_conflict")
        async with self.database.unit_of_work() as uow:
            session = uow.session
            campaign = await session.get(Campaign, campaign_id, with_for_update=True)
            if campaign is None:
                raise CampaignNotFound("This campaign does not exist.")
            if campaign.state in ("draft", "archived"):
                raise OverrideConflict("Publish the campaign (or use a non-archived one) first.")
            current = await active_override(session, campaign, now)
            if current is not None and current.kind == kind:
                raise OverrideConflict(f"The campaign is already manually {kind}d.")
            if current is not None:
                current.expired_at = now
            occurrence = await occurrence_at(session, campaign, now)
            if until is None:
                if kind == "activate":
                    until = occurrence.end_at if occurrence else None
                    if until is None:
                        raise ValidationFailed(
                            "Outside a scheduled window, give an end ('until').",
                            code="campaign.override_conflict",
                        )
                else:
                    until = await session.scalar(
                        select(Occurrence.start_at)
                        .where(
                            Occurrence.campaign_id == campaign.id,
                            Occurrence.status == "planned",
                            Occurrence.start_at > now,
                        )
                        .order_by(Occurrence.start_at)
                        .limit(1)
                    )
            override = Override(
                campaign_id=campaign.id,
                kind=kind,
                from_at=now,
                until_at=until,
                actor_user_id=actor_id(actor),
                reason=reason[:200],
                created_at=now,
            )
            session.add(override)
            if campaign.state == "ended":
                campaign.state = "scheduled"
            await session.flush()
            await self.reconciler.reconcile(session, campaign, now)
            await self.audit.record(
                session,
                AuditRecord(
                    action=f"campaign.{kind}d",
                    actor=actor,
                    resource=ResourceRef("campaign", str(campaign.id)),
                    decision="allow",
                    context={"campaign": campaign.key, "until": until.isoformat() if until else None},
                    sensitive=True,
                ),
            )
        metrics.increment(f"campaigns.overrides.{kind}")
        return override
