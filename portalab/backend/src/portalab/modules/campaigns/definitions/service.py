"""Campaign definitions (T007; R8): every save publishes an **append-only version** effective now (earlier
grants keep the version that was in force); future occurrences are re-planned from the new version; the
state machine is Draft → Scheduled → Active ⇄ Paused → Ended → Archived. Admin changes are audited."""

import re
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import CAPABILITY as THEME_CATALOG
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.campaigns.definitions.schema import CampaignDefinition, parse_definition
from portalab.modules.campaigns.intervals.manager import Intervals
from portalab.modules.campaigns.models import Campaign, CampaignVersion, Occurrence, OpenInterval
from portalab.modules.campaigns.planner.planner import Resolve, expand, resolve_wall_clock

KEY = r"^[a-z0-9][a-z0-9_-]{1,63}$"


class CampaignNotFound(NotFound):
    default_code = "campaign.not_found"
    default_title = "Campaign not found"


class NotEditable(Conflict):
    default_code = "campaign.not_editable"
    default_title = "This campaign can no longer be edited"


def actor_id(actor: Principal) -> UUID | None:
    return actor.acting_for or actor.user_id


class Definitions:
    def __init__(
        self,
        database: Database,
        audit: AuditSink,
        intervals: Intervals,
        capabilities: CapabilityRegistry,
        *,
        resolve: Callable[[], Resolve] = lambda: resolve_wall_clock,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.audit = audit
        self.intervals = intervals
        self.capabilities = capabilities
        self.resolve = resolve
        self.clock = clock

    async def _audit(
        self, session: AsyncSession, actor: Principal, action: str, campaign: Campaign, **context: Any
    ) -> None:
        await self.audit.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=ResourceRef("campaign", str(campaign.id)),
                decision="allow",
                context={"campaign": campaign.key, **context},
                sensitive=True,
            ),
        )

    async def validate(self, raw: Mapping[str, Any]) -> CampaignDefinition:
        definition = parse_definition(raw)
        if definition.theme is not None:
            providers = self.capabilities.system_providers(THEME_CATALOG)
            if providers and definition.theme.theme_key not in await providers[0].provider.allowed_keys():
                raise ValidationFailed(
                    "This theme does not exist or is not allowed.",
                    code="campaign.invalid_definition",
                    extensions={"errors": ["theme.theme_key: unknown theme"]},
                )
        return definition

    async def plan(
        self, session: AsyncSession, campaign: Campaign, definition: CampaignDefinition, now: datetime
    ) -> None:
        """Future occurrences follow the version just published; started and past ones are kept."""
        await session.execute(
            delete(Occurrence).where(Occurrence.campaign_id == campaign.id, Occurrence.status == "planned")
        )
        highest = await session.scalar(
            select(func.coalesce(func.max(Occurrence.index), -1)).where(Occurrence.campaign_id == campaign.id)
        )
        base = int(highest if highest is not None else -1) + 1
        current = (
            await session.execute(
                select(Occurrence).where(Occurrence.campaign_id == campaign.id, Occurrence.status == "active")
            )
        ).scalar_one_or_none()
        for window in expand(definition, self.resolve()):
            if window.end_at <= now or (window.start_at <= now and current is not None):
                continue
            session.add(
                Occurrence(
                    campaign_id=campaign.id,
                    version=campaign.current_version,
                    index=base + window.index,
                    start_at=window.start_at,
                    end_at=window.end_at,
                    status="planned",
                )
            )
        await session.flush()

    async def create(
        self, actor: Principal, key: str, raw: Mapping[str, Any], *, draft: bool = False
    ) -> Campaign:
        if not re.fullmatch(KEY, key):
            raise ValidationFailed("Invalid campaign key.", code="campaign.invalid_definition")
        definition = await self.validate(raw)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            if await session.scalar(select(Campaign.id).where(Campaign.key == key)) is not None:
                raise Conflict("A campaign with this key exists.", code="campaign.duplicate")
            campaign = Campaign(
                key=key,
                state="draft" if draft else "scheduled",
                current_version=1,
                timezone=definition.timezone,
                created_by=actor_id(actor),
                created_at=now,
            )
            session.add(campaign)
            await session.flush()
            session.add(
                CampaignVersion(
                    campaign_id=campaign.id,
                    version=1,
                    effective_from=now,
                    definition=definition.model_dump(mode="json"),
                    created_by=actor_id(actor),
                    created_at=now,
                )
            )
            if not draft:
                await self.plan(session, campaign, definition, now)
            await self._audit(session, actor, "campaign.created", campaign, version=1)
            await self.intervals.emit(
                session, "campaign.created", campaign, 1, now, actor=actor, dedup="created"
            )
            return campaign

    async def publish(self, actor: Principal, campaign_id: UUID, raw: Mapping[str, Any]) -> Campaign:
        definition = await self.validate(raw)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            campaign = await session.get(Campaign, campaign_id, with_for_update=True)
            if campaign is None:
                raise CampaignNotFound("This campaign does not exist.")
            if campaign.state in ("ended", "archived"):
                raise NotEditable("Ended or archived campaigns cannot be edited; create a new one.")
            campaign.current_version += 1
            campaign.timezone = definition.timezone
            session.add(
                CampaignVersion(
                    campaign_id=campaign.id,
                    version=campaign.current_version,
                    effective_from=now,
                    definition=definition.model_dump(mode="json"),
                    created_by=actor_id(actor),
                    created_at=now,
                )
            )
            if campaign.state == "draft":
                campaign.state = "scheduled"
            await self.plan(session, campaign, definition, now)
            open_row = await session.get(OpenInterval, campaign.id)
            if open_row is not None:
                open_row.version = campaign.current_version
            await self._audit(
                session, actor, "campaign.version_published", campaign, version=campaign.current_version
            )
            await self.intervals.emit(
                session,
                "campaign.version_published",
                campaign,
                campaign.current_version,
                now,
                actor=actor,
                dedup=f"version:{campaign.current_version}",
            )
            return campaign

    async def get(self, campaign_id: UUID) -> tuple[Campaign, CampaignDefinition]:
        async with self.database.session() as session:
            campaign = await session.get(Campaign, campaign_id)
            if campaign is None:
                raise CampaignNotFound("This campaign does not exist.")
            version = await session.get(CampaignVersion, (campaign.id, campaign.current_version))
        assert version is not None
        return campaign, CampaignDefinition.model_validate(version.definition)

    async def all(self) -> list[Campaign]:
        async with self.database.session() as session:
            return list(
                (await session.execute(select(Campaign).order_by(Campaign.created_at.desc()))).scalars()
            )

    async def cancel(self, actor: Principal, campaign_id: UUID, reason: str) -> Campaign:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            campaign = await session.get(Campaign, campaign_id, with_for_update=True)
            if campaign is None:
                raise CampaignNotFound("This campaign does not exist.")
            if campaign.state == "archived":
                raise NotEditable("This campaign is archived.")
            await self.intervals.close(session, campaign, now, actor=actor_id(actor), reason=reason)
            occurrences = (
                await session.execute(
                    select(Occurrence).where(
                        Occurrence.campaign_id == campaign.id, Occurrence.status.in_(("planned", "active"))
                    )
                )
            ).scalars()
            for occurrence in occurrences:
                occurrence.status = "cancelled" if occurrence.status == "planned" else "ended"
            campaign.state = "ended"
            await self._audit(session, actor, "campaign.cancelled", campaign, reason=reason[:200])
            await self.intervals.emit(
                session,
                "campaign.cancelled",
                campaign,
                campaign.current_version,
                now,
                actor=actor,
                dedup="cancelled",
            )
            return campaign

    async def archive(self, actor: Principal, campaign_id: UUID) -> Campaign:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            campaign = await session.get(Campaign, campaign_id, with_for_update=True)
            if campaign is None:
                raise CampaignNotFound("This campaign does not exist.")
            if campaign.state in ("active", "paused", "scheduled"):
                raise NotEditable("Cancel or let the campaign end before archiving it.")
            campaign.state, campaign.archived_at = "archived", now
            await self._audit(session, actor, "campaign.archived", campaign)
            await self.intervals.emit(
                session,
                "campaign.archived",
                campaign,
                campaign.current_version,
                now,
                actor=actor,
                dedup="archived",
            )
            return campaign
