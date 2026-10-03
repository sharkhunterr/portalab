"""Campaign contracts (spec 014, contracts/campaigns-contracts.md).

A *campaign* is a time-bound themed context (≠ a domain event, CD-009). The Campaigns module implements:
* ``economy.modifiers`` (013 ``ModifierProvider``) — factors with ``campaign:<key>:<version>:<modifier>``
  references for occurrences inside an activation interval; never amounts (combination is 013's CD-024);
* ``economy.definition_sources`` (013 ``DefinitionSource``) — campaign-scoped achievements while active;
* ``campaigns.reader`` (``CampaignReader``: 009 ``campaign_active`` widget condition, 017 unlocks);
* ``campaigns.content`` (``CampaignContentProvider``) and the 011 ``CalendarSource(kind="campaign")``.
Domain attributes for conditions come from ``activity.attributes`` providers (e.g. Media 024)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec
from portalab.capabilities.statistics import CAMPAIGNS as READER

CONTENT = "campaigns.content"


@dataclass(frozen=True, slots=True)
class CampaignRef:
    key: str
    name: str
    version: int
    started_at: datetime
    ends_at: datetime | None = None
    theme_key: str | None = None
    presentation_priority: int = 0


@dataclass(frozen=True, slots=True)
class ScopedDefinition:
    key: str
    campaign: str
    version: int
    definition: dict[str, Any] = field(default_factory=dict)
    active_from: datetime | None = None


@runtime_checkable
class CampaignReader(Protocol):
    async def is_active(self, campaign: str, at: datetime | None = None) -> bool: ...

    async def active_for_user(self, user: UUID, at: datetime | None = None) -> Sequence[CampaignRef]: ...


@runtime_checkable
class CampaignContentProvider(Protocol):
    async def achievements_active_at(self, at: datetime) -> Sequence[ScopedDefinition]: ...

    async def quests_active_at(self, at: datetime) -> Sequence[ScopedDefinition]: ...


CONTENT_SPEC = CapabilitySpec(
    name=CONTENT,
    version="1.0",
    protocol=CampaignContentProvider,
    multi_provider=False,
    description="Campaign-scoped achievements and quests active at an instant (Campaigns 014)",
)
SPECS: tuple[CapabilitySpec, ...] = (CONTENT_SPEC,)
__all__ = [
    "CONTENT",
    "READER",
    "CampaignContentProvider",
    "CampaignReader",
    "CampaignRef",
    "ScopedDefinition",
]
