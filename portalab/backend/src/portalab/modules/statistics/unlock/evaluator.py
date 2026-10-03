"""``UnlockEvaluator`` (T019; R6): closed-set unlock conditions evaluated through the owners' ports —
``level_at_least`` / ``achievement_earned`` (013 ``ProgressionReader``), ``product_owned`` (015
``EntitlementReader``), ``campaign_active`` (014 ``CampaignReader``), ``all_of`` / ``any_of``.

Fail closed: a missing or failing port means *locked*. Permanent unlocks (level, achievement) are
persisted in ``stats.unlocks`` and announced once (``statistics.unlocked``); campaign/product conditions
re-lock when they stop holding (re-evaluated on every access)."""

from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.dashboard import ENTITLEMENTS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.statistics import CAMPAIGNS, PROGRESSION, StatisticDefinition, UnlockCondition
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.statistics.models import Unlock
from portalab.modules.statistics.observability import log

RELOCKING = frozenset({"campaign_active", "product_owned"})


def relocks(condition: UnlockCondition) -> bool:
    if condition.kind in RELOCKING:
        return True
    return any(relocks(child) for child in condition.conditions)


def hint_of(definition: StatisticDefinition) -> str:
    unlock = definition.unlock
    assert unlock is not None
    return unlock.hint_key or f"statistics:unlock.{unlock.condition.kind}"


class UnlockEvaluator:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.clock = clock

    def _port(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def locked(self, user_id: UUID | None, definition: StatisticDefinition) -> tuple[bool, str | None]:
        """``(locked, hint)`` — nothing about the statistic is computed while it is locked."""
        unlock = definition.unlock
        if unlock is None:
            return False, None
        if user_id is None:
            return True, hint_of(definition)
        relock = unlock.relock if unlock.relock is not None else relocks(unlock.condition)
        if not relock:
            async with self.database.session() as session:
                if await session.get(Unlock, (user_id, definition.key)) is not None:
                    return False, None
        try:
            passed = await self._holds(unlock.condition, user_id)
        except Exception:
            log.warning("unlock condition unavailable", extra={"stat": definition.key})
            passed = False  # fail closed
        if not passed:
            return True, hint_of(definition)
        if not relock:
            await self._persist(user_id, definition, unlock.condition)
        return False, None

    async def _holds(self, condition: UnlockCondition, user_id: UUID) -> bool:
        match condition.kind:
            case "all_of":
                return (
                    all([await self._holds(child, user_id) for child in condition.conditions])
                    if condition.conditions
                    else False
                )
            case "any_of":
                for child in condition.conditions:
                    if await self._holds(child, user_id):
                        return True
                return False
            case "level_at_least":
                progression = self._port(PROGRESSION)
                return progression is not None and await progression.level(user_id) >= int(
                    condition.value or 0
                )
            case "achievement_earned":
                progression = self._port(PROGRESSION)
                return progression is not None and await progression.has_achievement(
                    user_id, str(condition.value)
                )
            case "product_owned":
                entitlements = self._port(ENTITLEMENTS)
                return entitlements is not None and await entitlements.owns(user_id, str(condition.value))
            case "campaign_active":
                campaigns = self._port(CAMPAIGNS)
                return campaigns is not None and await campaigns.is_active(str(condition.value))
        return False

    async def _persist(
        self, user_id: UUID, definition: StatisticDefinition, condition: UnlockCondition
    ) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            inserted = (
                await uow.session.execute(
                    insert(Unlock)
                    .values(
                        user_id=user_id,
                        stat_key=definition.key,
                        unlocked_at=now,
                        reason=condition.model_dump(mode="json"),
                    )
                    .on_conflict_do_nothing()
                    .returning(Unlock.stat_key)
                )
            ).scalar_one_or_none()
            if inserted is not None:
                await self.events.publish(
                    uow.session,
                    "statistics.unlocked",
                    {"statistic": definition.key},
                    occurred_at=now,
                    actor=None,
                    subject=SubjectRef("user", str(user_id)),
                    source="statistics",
                    dedup_key=f"statistics.unlocked:{user_id}:{definition.key}",
                )
