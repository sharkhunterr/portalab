"""Level rewards (027): reaching a level gives what the administrator set for it — Coins, Contribution, a
shop product offered (``marketplace.gifts``). Consumes ``user.level_up``; every tier up to the level
reached is given once (ledger idempotency; a product owned already is skipped), so jumping several levels
at once misses nothing."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.capabilities.marketplace import GIFTS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.modules.gamification.ledger.writer import Entry, LedgerWriter
from portalab.modules.gamification.observability import log

CONSUMER = "gamification.level_rewards"
OWNER = "module:gamification"


class LevelReward(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    level: int = Field(ge=2, le=1000)
    coins: int = Field(default=0, ge=0, le=1_000_000)
    contribution: int = Field(default=0, ge=0, le=1_000_000)
    product: str | None = Field(default=None, max_length=96)
    label: str = Field(default="", max_length=120)


def parse_rewards(raw: Any) -> list[LevelReward]:
    out: list[LevelReward] = []
    for item in raw or []:
        try:
            out.append(LevelReward.model_validate(item))
        except ValidationError:
            continue
    return sorted(out, key=lambda r: r.level)


class LevelRewards:
    def __init__(
        self,
        database: Database,
        writer: LedgerWriter,
        capabilities: CapabilityRegistry,
        config: Callable[[], Any],
    ) -> None:
        self.database = database
        self.writer = writer
        self.capabilities = capabilities
        self.config = config

    def consumer(self) -> Consumer:
        return Consumer(CONSUMER, frozenset({"user.level_up"}), self.handle, OWNER)

    async def handle(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        level = int((envelope.payload or {}).get("level") or 0)
        if envelope.subject_type != "user" or not envelope.subject_id or level < 2:
            return
        await self.give(UUID(envelope.subject_id), level, envelope.occurred_at)

    async def give(self, user: UUID, level: int, at: datetime) -> int:
        given = 0
        for tier in parse_rewards(self.config().level_rewards):
            if tier.level > level:
                break
            for value, amount in (("coins", tier.coins), ("contribution", tier.contribution)):
                if amount <= 0:
                    continue
                async with self.database.unit_of_work() as uow:
                    recorded = await self.writer.record(
                        uow.session,
                        Entry(
                            user_id=user,
                            value=value,
                            delta=amount,
                            kind="grant",
                            source_kind="level_reward",
                            source_ref=f"level:{tier.level}",
                            idempotency_key=f"level_reward:{user}:{tier.level}:{value}",
                            occurred_at=at,
                        ),
                    )
                given += 0 if recorded.duplicate else 1
            if tier.product:
                gifts = self.capabilities.system_providers(GIFTS)
                if gifts:
                    try:
                        offered = await gifts[0].provider.gift(user, tier.product, f"level {tier.level}")
                        given += 1 if offered else 0
                    except Exception:
                        log.warning("level reward product not offered")
        return given
