"""The assistant's capacities bought in the shop (issue 173) — provided as ``ai.perks`` to the marketplace,
which grants one per purchase and withdraws it on a revoke. What a member holds now (``Upgrade``) raises their
day's allowance (to the administrators' ceiling), adds a recharge spent past it, and, for a turn, swaps the
model, the reflection, the memory and the tools for the administrators' stronger ones. A perk the
administrators no longer offer has no effect — and cannot be bought."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.ai import PERK_KINDS
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.ai.models import Perk
from portalab.modules.ai.settings import AiConfig

MAX_HOURS = 24 * 366
MAX_AMOUNT = 100_000_000


@dataclass(frozen=True, slots=True)
class Upgrade:
    """What a member holds today, as the administrators allow it."""

    daily_tokens: int = 0
    recharge: int = 0
    model: bool = False
    reflection: bool = False
    context: bool = False
    tools: bool = False
    until: dict[str, str] | None = None  # perk → when its last grant ends (ISO), for the member to see

    def apply(self, config: AiConfig) -> AiConfig:
        """The turn's settings with what was bought."""
        changes: dict[str, object] = {}
        if self.model and config.premium_model:
            changes["provider_model"] = config.premium_model
        if self.reflection and config.premium_reasoning:
            changes["provider_reasoning"] = config.premium_reasoning
        if self.context:
            changes["max_context_tokens"] = max(config.max_context_tokens, config.premium_context_tokens)
            changes["max_tool_calls_per_turn"] = max(
                config.max_tool_calls_per_turn, config.premium_tool_calls
            )
        return replace(config, **changes) if changes else config  # type: ignore[arg-type]

    @property
    def any(self) -> bool:
        return bool(
            self.daily_tokens or self.recharge or self.model or self.reflection or self.context or self.tools
        )


def allowance(config: AiConfig, upgrade: Upgrade) -> int:
    """A member's day: the portal's budget and what they bought, up to the administrators' ceiling."""
    day = config.daily_token_budget_per_user + upgrade.daily_tokens
    ceiling = config.max_daily_tokens_per_user
    return min(day, max(ceiling, config.daily_token_budget_per_user)) if ceiling > 0 else day


def offerable(config: AiConfig, perk: str) -> bool:
    """Whether the portal offers this perk now (the stronger model needs one named)."""
    if perk not in PERK_KINDS or perk not in config.perks_offered:
        return False
    if perk == "model":
        return bool(config.premium_model)
    if perk == "tools":
        return bool(config.premium_tools)
    return True


class Perks:
    def __init__(
        self, database: Database, config: Callable[[], AiConfig], *, clock: Clock | None = None
    ) -> None:
        self.database = database
        self.config = config
        self.clock = clock

    # --- ai.perks (the marketplace) -------------------------------------------------------------------
    def offers(self, perk: str) -> bool:
        return offerable(self.config(), perk)

    async def grant(self, user: UUID, perk: str, amount: int, hours: int, source_ref: str) -> bool:
        config = self.config()
        if not offerable(config, perk):
            return False
        amount = max(0, min(int(amount), MAX_AMOUNT))
        if perk in ("daily_tokens", "recharge") and amount <= 0:
            return False
        now = utc_now(self.clock)
        hours = max(0, min(int(hours), MAX_HOURS))
        expires = now + timedelta(hours=hours) if hours and perk != "recharge" else None
        remaining = amount if perk == "recharge" else 0
        if perk == "recharge" and config.max_recharge_tokens > 0:
            held = (await self.upgrade(user)).recharge
            remaining = max(0, min(remaining, config.max_recharge_tokens - held))
            if remaining <= 0:
                return False
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(Perk)
                .values(
                    user_id=user,
                    perk=perk,
                    amount=amount,
                    remaining=remaining,
                    source_ref=source_ref[:200],
                    created_at=now,
                    expires_at=expires,
                )
                .on_conflict_do_nothing(index_elements=["source_ref"])
            )
        return True

    async def revoke(self, source_ref: str) -> None:
        async with self.database.unit_of_work() as uow:
            row = (
                await uow.session.execute(select(Perk).where(Perk.source_ref == source_ref[:200]))
            ).scalar_one_or_none()
            if row is not None:
                await uow.session.delete(row)

    # --- what a member holds --------------------------------------------------------------------------
    async def upgrade(self, user: UUID) -> Upgrade:
        config = self.config()
        now = utc_now(self.clock)
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(Perk).where(
                            Perk.user_id == user, or_(Perk.expires_at.is_(None), Perk.expires_at > now)
                        )
                    )
                ).scalars()
            )
        held = [r for r in rows if offerable(config, r.perk)]
        until: dict[str, str] = {}
        for row in held:
            end = "forever" if row.expires_at is None else row.expires_at.isoformat()
            current = until.get(row.perk)
            if current != "forever" and (current is None or end == "forever" or end > current):
                until[row.perk] = end
        kinds = {r.perk for r in held}
        return Upgrade(
            daily_tokens=sum(r.amount for r in held if r.perk == "daily_tokens"),
            recharge=sum(r.remaining for r in held if r.perk == "recharge"),
            model="model" in kinds,
            reflection="reflection" in kinds,
            context="context" in kinds,
            tools="tools" in kinds,
            until={k: v for k, v in until.items() if k != "recharge"},
        )

    async def spend(self, user: UUID, tokens: int) -> int:
        """Spend ``tokens`` from the member's recharges, the oldest first; what could not be spent."""
        left = max(0, tokens)
        if not left:
            return 0
        async with self.database.unit_of_work() as uow:
            rows = (
                await uow.session.execute(
                    select(Perk)
                    .where(Perk.user_id == user, Perk.perk == "recharge", Perk.remaining > 0)
                    .order_by(Perk.created_at)
                    .with_for_update()
                )
            ).scalars()
            for row in rows:
                if not left:
                    break
                taken = min(row.remaining, left)
                await uow.session.execute(
                    update(Perk).where(Perk.id == row.id).values(remaining=Perk.remaining - taken)
                )
                left -= taken
        return left
