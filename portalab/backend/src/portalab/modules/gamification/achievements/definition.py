"""Achievement definitions (T025/T026; R11): one-time, versioned, closed criteria (all must hold) —
``event_count(event_type, filter) ≥ N`` (counters), ``level_at_least``, ``value_at_least``,
``statistic_at_least`` (017) — and optional rewards recorded through the ledger."""

from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from portalab.core.errors import ValidationFailed
from portalab.modules.gamification.rules.definition import Condition


class EventCount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["event_count"]
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$", max_length=128)
    filter: list[Condition] = Field(default_factory=list, max_length=5)
    count: int = Field(ge=1, le=1_000_000)


class LevelAtLeast(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["level_at_least"]
    level: int = Field(ge=1, le=1000)


class ValueAtLeast(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["value_at_least"]
    value: Literal["xp", "contribution", "coins"]
    amount: int = Field(ge=1, le=1_000_000_000)


class StatisticAtLeast(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["statistic_at_least"]
    statistic: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$", max_length=96)
    amount: float = Field(ge=0)


Criterion = Annotated[
    EventCount | LevelAtLeast | ValueAtLeast | StatisticAtLeast, Field(discriminator="kind")
]


class Reward(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    value: Literal["xp", "contribution", "coins"]
    amount: int = Field(ge=1, le=1_000_000)


class Unlock(BaseModel):
    """027: a shop product the achievement gives (a badge, a title, a frame, a background, a level badge…),
    with the words shown to members — reward-only products are not in the shop's public listing."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    product: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,95}$")
    kind: Literal[
        "badge", "title", "avatar_frame", "profile_banner", "profile_background", "name_style", "level_badge",
        "level_up", "notification_style", "notification_animation", "effect", "ambient", "palette", "theme",
    ]  # fmt: skip
    label: str = Field(min_length=1, max_length=80)


class AchievementDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    label: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)
    icon: str | None = Field(default=None, max_length=64)
    hidden: bool = False
    # 027 US9: what the achievement rewards (shown as a filter, like game platforms)
    category: Literal[
        "service_usage", "purchase", "community", "progression", "events", "content", "other"
    ] = "other"
    criteria: list[Criterion] = Field(min_length=1, max_length=5)
    rewards: list[Reward] = Field(default_factory=list, max_length=3)
    unlocks: list[Unlock] = Field(default_factory=list, max_length=4)  # 027: cosmetics it gives


_ADAPTER = TypeAdapter(AchievementDefinition)


def parse_achievement(raw: Mapping[str, Any]) -> AchievementDefinition:
    try:
        return _ADAPTER.validate_python(dict(raw))
    except ValidationError as exc:
        raise ValidationFailed(
            "This achievement is not valid.",
            code="economy.achievement_invalid",
            extensions={"errors": [e["msg"][:200] for e in exc.errors()][:10]},
        ) from exc
