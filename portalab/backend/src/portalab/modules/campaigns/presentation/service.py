"""Presentation, reader and calendar (T024, T028; R10, R12):

* ``for_user`` — campaigns active now for this user (audience-filtered) and the effective theme overlay:
  the highest-priority campaign theme still allowed by the 022 policy, unless the user opted out
  (``ui.campaignThemes = ignore``); accessibility preferences are applied by the SPA after it. Presentation
  never changes permissions or state.
* ``CampaignReader`` — ``is_active(key, at)`` (009 ``campaign_active`` condition, 017 unlocks) and
  ``active_for_user``.
* ``CalendarSource(kind="campaign")`` — occurrences in a range (011)."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.campaigns import CampaignRef
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.content import CalendarItem, CalendarSourceResult
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import CAPABILITY as THEME_CATALOG
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.campaigns.definitions.schema import CampaignDefinition
from portalab.modules.campaigns.matching.conditions import Matcher
from portalab.modules.campaigns.models import Campaign, CampaignVersion, Occurrence
from portalab.modules.campaigns.permissions import READ
from portalab.modules.campaigns.resolver.active import ActiveCampaign, ActiveResolver


def visible_to(campaign: ActiveCampaign) -> list[Any]:
    return [m.when.audience for m in campaign.definition.modifiers]


class Presentation:
    def __init__(
        self,
        database: Database,
        resolver: ActiveResolver,
        matcher: Matcher,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.resolver = resolver
        self.matcher = matcher
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock

    async def _for(self, user: UUID, campaign: ActiveCampaign) -> bool:
        """A campaign concerns a user when one of its modifiers' audiences includes them (or it has none)."""
        audiences = visible_to(campaign)
        if not audiences:
            return True
        for audience in audiences:
            if await self.matcher.in_audience(audience, user):
                return True
        return False

    def _ref(self, campaign: ActiveCampaign, language: str = "en") -> CampaignRef:
        theme = campaign.definition.theme
        return CampaignRef(
            campaign.key,
            campaign.definition.name(language),
            campaign.version,
            campaign.started_at,
            campaign.ends_at,
            theme.theme_key if theme else None,
            theme.presentation_priority if theme else 0,
        )

    async def active_for_user(self, user: UUID, at: datetime | None = None) -> Sequence[CampaignRef]:
        at = at or utc_now(self.clock)
        return [self._ref(c) for c in await self.resolver.at(at) if await self._for(user, c)]

    async def is_active(self, campaign: str, at: datetime | None = None) -> bool:
        return any(c.key == campaign for c in await self.resolver.at(at or utc_now(self.clock)))

    async def _opted_out(self, user: UUID) -> bool:
        providers = self.capabilities.system_providers(CONFIG)
        if not providers:
            return False
        try:
            return bool(
                (await providers[0].provider.get("ui.campaignThemes", user_id=user)).value == "ignore"
            )
        except Exception:
            return False

    async def presentation(self, user: UUID) -> dict[str, Any]:
        active = list(await self.active_for_user(user))
        theme: dict[str, Any] | None = None
        themed = sorted((c for c in active if c.theme_key), key=lambda c: (-c.presentation_priority, c.key))
        if themed and not await self._opted_out(user):
            catalog = self.capabilities.system_providers(THEME_CATALOG)
            allowed = await catalog[0].provider.allowed_keys() if catalog else frozenset()
            for campaign in themed:
                if campaign.theme_key in allowed:
                    theme = {"campaign": campaign.key, "theme_key": campaign.theme_key}
                    break
        return {
            "campaigns": [{"key": c.key, "name": c.name, "ends_at": c.ends_at} for c in active],
            "theme": theme,
        }

    # --- 011 calendar source -----------------------------------------------------------------------------
    kind = "campaign"
    label_key = "campaigns:calendar.source"

    async def items(
        self, start: datetime, end: datetime, viewer: Principal, ctx: LocaleContext
    ) -> CalendarSourceResult:
        if not await self.authorizer.is_allowed(viewer, READ):
            return CalendarSourceResult((), "ok", utc_now(self.clock))
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Occurrence, Campaign)
                    .join(Campaign, Campaign.id == Occurrence.campaign_id)
                    .where(
                        Occurrence.start_at < end,
                        Occurrence.end_at > start,
                        Occurrence.status != "cancelled",
                        Campaign.state != "archived",
                    )
                    .order_by(Occurrence.start_at)
                )
            ).all()
            names: dict[tuple[UUID, int], str] = {}
            for occurrence, campaign in rows:
                if (campaign.id, occurrence.version) not in names:
                    version = await session.get(CampaignVersion, (campaign.id, occurrence.version))
                    names[(campaign.id, occurrence.version)] = (
                        CampaignDefinition.model_validate(version.definition).name(ctx.language)
                        if version
                        else campaign.key
                    )
        items = [
            CalendarItem(
                source_kind="campaign",
                source_id=str(occurrence.id),
                type="campaign",
                title=names[(campaign.id, occurrence.version)],
                starts_at=occurrence.start_at,
                ends_at=occurrence.end_at,
                reference_tz=campaign.timezone,
                status="cancelled" if occurrence.status == "cancelled" else "scheduled",
                url_ref=f"/campaigns/{campaign.key}",
            )
            for occurrence, campaign in rows
        ]
        return CalendarSourceResult(items, "ok", utc_now(self.clock))

    async def item(self, source_id: str, viewer: Principal) -> CalendarItem | None:
        try:
            occurrence_id = UUID(source_id)
        except ValueError:
            return None
        if not await self.authorizer.is_allowed(viewer, READ):
            return None
        async with self.database.session() as session:
            occurrence = await session.get(Occurrence, occurrence_id)
            campaign = await session.get(Campaign, occurrence.campaign_id) if occurrence else None
        if occurrence is None or campaign is None:
            return None
        return CalendarItem(
            source_kind="campaign",
            source_id=source_id,
            type="campaign",
            title=campaign.key,
            starts_at=occurrence.start_at,
            ends_at=occurrence.end_at,
            reference_tz=campaign.timezone,
            url_ref=f"/campaigns/{campaign.key}",
        )
