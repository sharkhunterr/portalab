"""Issue 226: what a daily objective, a quest, a challenge, a discovery mission, an achievement, a level's
reward, a recognised contribution or an automation's grant earns follows the same bonuses as an action's —
the play streak, the campaigns, a boost bought, the overall pace —, combined and capped at
``economy.maxTotalBoost``, the detail kept in the ledger (« dont +x · Bonus de série »). A source the
administrators leave out of ``economy.rewardBonuses`` keeps its amount; the daily wheel never has any (a
draw), nor an administrator's manual grant.

The modifiers are asked about a synthetic occurrence ``gamification.reward.<source>`` (never stored): a
campaign bound to some activities only does not boost the rewards, one for everything does. The streak is
read, never counted: a reward does not keep a streak alive."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from portalab.capabilities.economy import Value
from portalab.modules.gamification.modifiers.combiner import Combined, ModifierCombiner, combine
from portalab.modules.gamification.rules.simulate import envelope
from portalab.modules.gamification.streaks.service import Streaks

REWARD_EVENT = "gamification.reward"
SOURCES = (
    "daily",
    "quest",
    "challenge",
    "discovery",
    "achievement",
    "level_reward",
    "contribution",
    "automation",
)


class RewardBonuses:
    def __init__(self, combiner: ModifierCombiner, streaks: Streaks, config: Callable[[], Any]) -> None:
        self.combiner = combiner
        self.streaks = streaks
        self.config = config

    async def combined(self, user: UUID, source: str, value: Value, at: datetime) -> Combined:
        config = self.config()
        if source not in (config.reward_bonuses or ()):
            return combine(1.0, [], config.max_total_boost)
        event = envelope(f"{REWARD_EVENT}.{source}", {"source": source}, user, at)
        found, unavailable = await self.combiner.modifiers(user, event, value, at)
        found = [*found, *await self.streaks.bonus(user, value, at)]
        return combine(1.0, found, config.max_total_boost, unavailable=unavailable)


async def boosted(
    bonuses: RewardBonuses | None, user: UUID, source: str, value: str, base: int, at: datetime
) -> dict[str, Any]:
    """A reward's ledger fields with its bonuses: its amount, and the multiplier and modifiers that made it
    (its base amount is the reward's own)."""
    if bonuses is None or value not in ("xp", "coins", "contribution") or base <= 0:
        return {"delta": base}
    combined = await bonuses.combined(user, source, value, at)  # type: ignore[arg-type]
    if len(combined.applied) <= 1 and not combined.unavailable:
        return {"delta": base}  # nothing but its own amount
    return {
        "delta": combined.apply(base),
        "multiplier": round(combined.factor, 4),
        "modifiers": combined.record(),
    }
