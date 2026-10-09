"""Integrations (T003, T030, T033): the ``progression`` visibility datum and its owner-held preference
(021), the dashboard widget ``gamification.progress`` (009), the AI tool ``progression.get`` (018) and the
automation actions ``award.xp|coins|contribution`` / ``reward.unlock`` (019)."""

from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.ai import AITool, AIToolRegistry, SourceRef, ToolResult
from portalab.capabilities.automation_actions import ActionRegistry, ActionType
from portalab.capabilities.dashboard import (
    Refresh,
    Size,
    SizeLimits,
    WidgetDefinition,
    WidgetPayload,
    with_styles,
)
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.visibility import Level, register_datum_class
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.manual.service import RewardServiceImpl
from portalab.modules.gamification.models import ProgressionPreference
from portalab.modules.gamification.permissions import GRANT, READ
from portalab.modules.gamification.progression.service import ProgressionService

OWNER = "module:gamification"
PROGRESSION = "progression"

register_datum_class(
    PROGRESSION,
    owner=OWNER,
    default_level="private",
    classification="activity",
    description="My level, XP, Contribution, Coins and achievements",
)


class ProgressionPreferences:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def get_preference(self, subject: UUID, datum_class: str, datum_ref: str | None) -> Level | None:
        if datum_class != PROGRESSION:
            return None
        async with self.database.session() as session:
            row = await session.get(ProgressionPreference, subject)
        return cast(Level, row.level) if row else None

    async def set_preference(
        self, subject: UUID, datum_class: str, datum_ref: str | None, level: Level
    ) -> None:
        if datum_class != PROGRESSION:
            raise ValidationFailed("Unknown datum class.", code="privacy.datum_not_found")
        statement = insert(ProgressionPreference).values(
            user_id=subject, level=level, updated_at=utc_now(self.clock)
        )
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[ProgressionPreference.user_id],
                    set_={"level": level, "updated_at": utc_now(self.clock)},
                )
            )


PROGRESS_WIDGET = WidgetDefinition(
    key="gamification.progress",
    owner=OWNER,
    title_key="gamification:widget.progress.title",
    description_key="gamification:widget.progress.description",
    icon="trophy",
    required_permission=READ,
    size=SizeLimits(default=Size(4, 2), min=Size(3, 1), max=Size(6, 4)),  # 027: one row = compact
    refresh=Refresh(mode="event", events=("reward.granted", "user.level_up", "achievement.unlocked")),
    stale_after_s=900,
    component_id="gamification.progress",
)


class ProgressWidget:
    def __init__(self, progression: ProgressionService, clock: Clock | None = None) -> None:
        self.progression = progression
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        if user is None:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        progress = await self.progression.progress(user)
        return WidgetPayload(
            "available",
            as_of=utc_now(self.clock),
            data={
                "level": progress.level,
                "xp": progress.xp,
                "next_level_at": progress.next_level_at,
                "level_floor": progress.level_floor,
                "contribution": progress.contribution,
                "coins": progress.coins,
            },
        )


DAILY_WIDGET = WidgetDefinition(
    key="gamification.daily_objectives",
    owner=OWNER,
    title_key="gamification:widget.daily.title",
    description_key="gamification:widget.daily.description",
    icon="target",
    required_permission=READ,
    size=SizeLimits(default=Size(4, 2), min=Size(3, 1), max=Size(6, 4)),  # 027: one row = compact
    refresh=Refresh(mode="event", events=("quest.completed", "reward.granted")),
    stale_after_s=900,
    component_id="gamification.daily_objectives",
)


class DailyObjectivesWidget:
    """Today's daily objectives of the viewer, with step progress (own data only)."""

    def __init__(self, quests: Any, clock: Clock | None = None) -> None:
        self.quests = quests
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        user = principal.acting_for or principal.user_id
        if user is None:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        items = await self.quests.mine(user, kinds=("daily",))
        if not items:
            return WidgetPayload("no-data", as_of=utc_now(self.clock))
        return WidgetPayload("available", as_of=utc_now(self.clock), data={"items": items})


def progression_tool(progression: ProgressionService, clock: Clock | None = None) -> AITool:
    async def handler(principal: Principal, params: Mapping[str, Any]) -> ToolResult:
        user = principal.acting_for or principal.user_id
        if user is None:
            return ToolResult("error", detail="no user")
        progress = await progression.progress(user)
        return ToolResult(
            "ok",
            {
                "level": progress.level,
                "xp": progress.xp,
                "next_level_at": progress.next_level_at,
                "contribution": progress.contribution,
                "coins": progress.coins,
                "achievements": progress.achievements,
            },
            (
                SourceRef(
                    "progression",
                    f"progression:{user}",
                    "My progression",
                    "real",
                    utc_now(clock),
                    "/progression",
                ),
            ),
        )

    return AITool(
        name="progression.get",
        description="The user's own level, XP, Contribution, Coins and achievement count.",
        params_schema={"type": "object", "properties": {}, "additionalProperties": False},
        required_permission=READ,
        sensitivity="read",
        handler=handler,
        owner=OWNER,
    )


def register_tools(
    registry: AIToolRegistry, progression: ProgressionService, clock: Clock | None = None
) -> None:
    if registry.get("progression.get") is None:
        registry.register(progression_tool(progression, clock))


def register_actions(rewards: RewardServiceImpl, registry: ActionRegistry) -> None:
    def award(value: str) -> Any:
        async def run(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
            transaction = await rewards.grant_via_automation(
                principal,
                UUID(str(params["user"])),
                value,  # type: ignore[arg-type]
                int(params["amount"]),
                automation_ref=str(params.get("automation", "automation")),
                idempotency_key=str(params["idempotency"]),
            )
            return {
                "transaction": str(transaction.id) if transaction else None,
                "withheld": transaction is None,
            }

        return run

    async def unlock(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        unlocked = await rewards.unlock(principal, UUID(str(params["user"])), str(params["achievement"]))
        return {"unlocked": unlocked}

    schema = {"user": "uuid", "amount": "integer", "idempotency": "string", "automation": "string"}
    for value in ("xp", "coins", "contribution"):
        if registry.get(f"award.{value}") is None:
            registry.register(
                ActionType(
                    key=f"award.{value}",
                    description=f"Grant {value} to a user (anti-abuse applies)",
                    permission=GRANT,
                    idempotency="ledger idempotency key automation:<idempotency>",
                    run=award(value),
                    owner=OWNER,
                    params_schema=schema,
                )
            )
    if registry.get("reward.unlock") is None:
        registry.register(
            ActionType(
                key="reward.unlock",
                description="Unlock an achievement for a user (once)",
                permission=GRANT,
                idempotency="unique (user, achievement)",
                run=unlock,
                owner=OWNER,
                params_schema={"user": "uuid", "achievement": "string"},
            )
        )


class CatalogFacade:
    """``economy.catalog`` (slice C): 013's own achievement and quest views for presentation surfaces."""

    def __init__(self, achievements: Any, progression: ProgressionService, quests: Any) -> None:
        self.achievements = achievements
        self.progression = progression
        self.quests = quests

    async def achievements_of(self, user_id: UUID) -> list[dict[str, Any]]:
        return list(await self.achievements.progress(user_id))

    async def unlocked_of(self, user_id: UUID, limit: int = 50) -> list[dict[str, str]]:
        return await self.progression.achievement_list(user_id, limit)

    async def quests_of(self, user_id: UUID) -> list[dict[str, Any]]:
        return list(await self.quests.mine(user_id))


PROGRESS_WIDGET = with_styles(PROGRESS_WIDGET, "odometer", "chart")  # 027 (#31)
DAILY_WIDGET = with_styles(DAILY_WIDGET, "liquid")  # 027 (#31)
