"""Gamification events (T003; via 007, no PII): ``reward.granted`` (aggregatable value/amount/source),
``user.level_up``, ``achievement.unlocked``, ``economy.coins_spent|refunded|destroyed``,
``economy.anomaly_flagged``, ``economy.rule_published``. The subject is the user; payloads carry ids and
numbers only."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:gamification"
OWN_TYPES = frozenset(
    {
        "reward.granted",
        "user.level_up",
        "achievement.unlocked",
        "quest.completed",
        "economy.coins_spent",
        "economy.coins_refunded",
        "economy.coins_destroyed",
        "economy.anomaly_flagged",
        "economy.rule_published",
    }
)


class RewardGranted(BaseModel):
    value: str
    amount: int
    source: str
    rule: str | None = None
    version: int | None = None


class LevelUp(BaseModel):
    level: int


class AchievementUnlocked(BaseModel):
    achievement: str


class QuestCompleted(BaseModel):
    quest: str
    kind: str
    period: str


class CoinsMoved(BaseModel):
    amount: int
    source: str


class AnomalyFlagged(BaseModel):
    kind: str


class RulePublished(BaseModel):
    rule: str
    version: int


GOAL_TYPES = frozenset({"quest.completed", "achievement.unlocked", "user.level_up"})


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema, aggregatable, visibility in (
        ("reward.granted", RewardGranted, frozenset({"value", "amount", "source"}), "private"),
        ("user.level_up", LevelUp, frozenset({"level"}), "community"),
        ("achievement.unlocked", AchievementUnlocked, frozenset({"achievement"}), "community"),
        ("quest.completed", QuestCompleted, frozenset({"quest", "kind"}), "community"),
        ("economy.coins_spent", CoinsMoved, frozenset({"amount", "source"}), "private"),
        ("economy.coins_refunded", CoinsMoved, frozenset({"amount", "source"}), "private"),
        ("economy.coins_destroyed", CoinsMoved, frozenset({"amount"}), "restricted"),
        ("economy.anomaly_flagged", AnomalyFlagged, frozenset(), "restricted"),
        ("economy.rule_published", RulePublished, frozenset(), "restricted"),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    aggregatable=aggregatable,
                    # #309: what a quest or an achievement may test of the progression itself (the quest
                    # done, the achievement unlocked, the level reached) — never a reward rule's action
                    rewardable=aggregatable if name in GOAL_TYPES else frozenset(),
                    automatable=name
                    in ("user.level_up", "achievement.unlocked", "quest.completed", "reward.granted"),
                    visibility_class=visibility,  # type: ignore[arg-type]
                )
            )
