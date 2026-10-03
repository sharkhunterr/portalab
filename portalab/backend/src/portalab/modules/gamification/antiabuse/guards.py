"""Anti-abuse guards (T020/T022; R7), applied **after** multipliers and equally to XP, Contribution and
Coins — multipliers never bypass them:

1. cooldown — a repeat of the same rule for the same user within ``cooldown_seconds`` is withheld;
2. diminishing returns — the n-th repeat in the period is reduced (geometric or steps);
3. caps — the amount is trimmed to what remains of the period cap (rule-level, optionally per value);
4. anomaly — beyond ``maxGrantsPerHour`` or ``maxCoinsPerDay`` the grant is withheld and flagged.
Withheld grants are recorded (``withheld``), never silently dropped."""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.modules.gamification.antiabuse.windows import window_start
from portalab.modules.gamification.models import LedgerTransaction, UsageWindow
from portalab.modules.gamification.rules.definition import Limits
from portalab.modules.gamification.settings import EconomyConfig

GRANTS = "*grants"  # usage window across all sources: grant count per hour
COINS = "*coins"  # coins granted per day


@dataclass
class Verdict:
    amount: int
    withheld: str | None = None  # cooldown | cap | anomaly
    anomaly: str | None = None  # grants_per_hour | coins_per_day
    effects: dict[str, Any] = field(default_factory=dict)


async def _window(session: AsyncSession, user: UUID, key: str, kind: str, start: datetime) -> tuple[int, int]:
    row = await session.get(UsageWindow, (user, key, kind, start))
    return (row.count, row.amount) if row else (0, 0)


async def bump(session: AsyncSession, user: UUID, key: str, kind: str, start: datetime, amount: int) -> None:
    statement = insert(UsageWindow).values(
        user_id=user, rule_key=key, window_kind=kind, window_start=start, count=1, amount=amount
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[
                UsageWindow.user_id,
                UsageWindow.rule_key,
                UsageWindow.window_kind,
                UsageWindow.window_start,
            ],
            set_={"count": UsageWindow.count + 1, "amount": UsageWindow.amount + amount},
        )
    )


class Guards:
    def __init__(self, config: Any) -> None:
        self.config = config  # callable → EconomyConfig

    async def rule_guards(
        self,
        session: AsyncSession,
        user: UUID,
        rule_key: str,
        limits: Limits,
        value: str,
        amount: int,
        at: datetime,
    ) -> Verdict:
        config: EconomyConfig = self.config()
        verdict = Verdict(amount)
        if limits.cooldown_seconds:
            window = timedelta(seconds=limits.cooldown_seconds)
            recent = await session.scalar(
                select(func.count())
                .select_from(LedgerTransaction)
                .where(
                    LedgerTransaction.user_id == user,
                    LedgerTransaction.rule_key == rule_key,
                    LedgerTransaction.value == value,
                    LedgerTransaction.occurred_at > at - window,
                    LedgerTransaction.occurred_at < at + window,
                )
            )
            if recent:
                verdict.amount, verdict.withheld = 0, "cooldown"
                verdict.effects["cooldown_seconds"] = limits.cooldown_seconds
                return verdict
        if limits.diminishing is not None:
            curve = limits.diminishing
            start = window_start(curve.period, at, config.timezone)
            repeats, _ = await _window(session, user, f"{rule_key}:{value}", curve.period, start)
            factor = (
                curve.factor**repeats
                if curve.kind == "geometric"
                else curve.steps[min(repeats, len(curve.steps) - 1)]
            )
            if factor < 1:
                verdict.amount = math.floor(verdict.amount * factor)
                verdict.effects["diminishing"] = {"repeats": repeats, "factor": round(factor, 4)}
        for cap in limits.caps:
            if cap.value is not None and cap.value != value:
                continue
            start = window_start(cap.period, at, config.timezone)
            _, used = await _window(session, user, f"{rule_key}:{value}", cap.period, start)
            remaining = max(0, cap.max_amount - used)
            if verdict.amount > remaining:
                verdict.effects.setdefault("caps", []).append(
                    {"period": cap.period, "trimmed": verdict.amount - remaining}
                )
                verdict.amount = remaining
        if verdict.amount <= 0 and verdict.withheld is None:
            verdict.withheld = "cap"
        return verdict

    async def anomaly(
        self, session: AsyncSession, user: UUID, value: str, amount: int, at: datetime
    ) -> str | None:
        config: EconomyConfig = self.config()
        hour = window_start("hour", at, "UTC")
        grants, _ = await _window(session, user, GRANTS, "hour", hour)
        if config.anomaly_max_grants_per_hour and grants + 1 > config.anomaly_max_grants_per_hour:
            return "grants_per_hour"
        if value == "coins" and config.anomaly_max_coins_per_day:
            day = window_start("day", at, config.timezone)
            _, coins = await _window(session, user, COINS, "day", day)
            if coins + amount > config.anomaly_max_coins_per_day:
                return "coins_per_day"
        return None

    async def record(
        self,
        session: AsyncSession,
        user: UUID,
        rule_key: str | None,
        limits: Limits | None,
        value: str,
        amount: int,
        at: datetime,
    ) -> None:
        """Counts a granted amount in every window that guards it."""
        config: EconomyConfig = self.config()
        await bump(session, user, GRANTS, "hour", window_start("hour", at, "UTC"), amount)
        if value == "coins":
            await bump(session, user, COINS, "day", window_start("day", at, config.timezone), amount)
        if rule_key is None or limits is None:
            return
        periods = {cap.period for cap in limits.caps if cap.value in (None, value)}
        if limits.diminishing is not None:
            periods.add(limits.diminishing.period)
        for period in sorted(periods):
            await bump(
                session,
                user,
                f"{rule_key}:{value}",
                period,
                window_start(period, at, config.timezone),
                amount,
            )
