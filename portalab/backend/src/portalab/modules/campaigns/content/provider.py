"""Campaign content (T024; R9): campaign-scoped achievements (and quests, Slice C of 013) exposed while the
campaign is active — as 013 ``DefinitionSource`` (achievements evaluated and granted by Gamification's
ledger, no parallel reward path) and as ``CampaignContentProvider``."""

from collections.abc import Sequence
from datetime import datetime

from portalab.capabilities.campaigns import ScopedDefinition
from portalab.capabilities.economy import ExternalDefinition
from portalab.modules.campaigns.resolver.active import ActiveResolver


class CampaignContent:
    def __init__(self, resolver: ActiveResolver) -> None:
        self.resolver = resolver

    async def _scoped(self, at: datetime, kind: str) -> list[ScopedDefinition]:
        out = []
        for campaign in await self.resolver.at(at):
            for nested in getattr(campaign.definition, kind):
                out.append(
                    ScopedDefinition(
                        f"{campaign.key}.{nested.key}",
                        campaign.key,
                        campaign.version,
                        dict(nested.definition),
                        campaign.started_at,
                    )
                )
        return out

    async def achievements_active_at(self, at: datetime) -> Sequence[ScopedDefinition]:
        return await self._scoped(at, "achievements")

    async def quests_active_at(self, at: datetime) -> Sequence[ScopedDefinition]:
        return await self._scoped(at, "quests")

    async def quests(self, at: datetime) -> Sequence[ExternalDefinition]:
        """013 ``DefinitionSource`` (slice C): campaign quests and challenges, only while active."""
        return [
            ExternalDefinition(
                item.key,
                item.version,
                item.definition,
                item.active_from or at,
                None,
                f"campaign:{item.campaign}:{item.version}",
            )
            for item in await self.quests_active_at(at)
        ]

    async def achievements(self, at: datetime) -> Sequence[ExternalDefinition]:
        """013 ``DefinitionSource``."""
        return [
            ExternalDefinition(
                item.key,
                item.version,
                item.definition,
                item.active_from or at,
                None,
                f"campaign:{item.campaign}:{item.version}",
            )
            for item in await self.achievements_active_at(at)
        ]
