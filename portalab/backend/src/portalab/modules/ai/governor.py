"""Governor (T014; FR-024): kill switch, per-user rate limit (sliding minute), daily token budget from
``ai.usage_daily`` (fail-closed: an unreadable budget refuses), per-user and global concurrency caps."""

import threading
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.ai.errors import AiBudgetExceeded, AiRateLimited, AiUnavailable
from portalab.modules.ai.models import UsageDaily
from portalab.modules.ai.observability import metrics
from portalab.modules.ai.perks import Perks, Upgrade, allowance
from portalab.modules.ai.settings import AiConfig

PER_USER_CONCURRENCY = 2
GLOBAL_CONCURRENCY = 32


class Governor:
    def __init__(
        self,
        database: Database,
        config: Callable[[], AiConfig],
        *,
        clock: Clock | None = None,
        perks: Perks | None = None,
    ) -> None:
        self.perks = perks  # issue 173: what a member bought raises their day
        self.database = database
        self.config = config
        self.clock = clock
        self._hits: dict[UUID, deque[float]] = {}
        self._active: dict[UUID, int] = {}
        self._global = 0
        self._lock = threading.Lock()

    def today(self) -> date:
        return utc_now(self.clock).date()

    def _rate(self, user: UUID) -> None:
        now = time.monotonic()
        limit = max(1, self.config().rate_limit_per_minute)
        with self._lock:
            hits = self._hits.setdefault(user, deque())
            while hits and hits[0] <= now - 60:
                hits.popleft()
            if len(hits) >= limit:
                metrics.increment("ai.guard.rate_limited")
                raise AiRateLimited(
                    "You are sending messages too quickly; try again in a minute.",
                    extensions={"retry_after": int(hits[0] + 60 - now) + 1},
                )
            hits.append(now)

    async def used_today(self, user: UUID) -> int:
        async with self.database.session() as session:
            row = await session.get(UsageDaily, (user, self.today()))
        return 0 if row is None else row.tokens_in + row.tokens_out

    async def upgrade(self, user: UUID) -> Upgrade:
        if self.perks is None:
            return Upgrade()
        try:
            return await self.perks.upgrade(user)
        except Exception:
            metrics.increment("ai.perks.unreadable")
            return Upgrade()  # what was bought cannot be read: the portal's own day still holds

    async def allowance(self, user: UUID) -> tuple[int, Upgrade]:
        """The member's day (with what they bought, to the ceiling) and what they hold."""
        upgrade = await self.upgrade(user)
        return allowance(self.config(), upgrade), upgrade

    async def admit(self, user: UUID) -> None:
        """Refuses before any provider call: disabled, rate-limited or out of budget."""
        if not self.config().enabled:
            raise AiUnavailable("The assistant is turned off.")
        self._rate(user)
        try:
            used = await self.used_today(user)
        except Exception as exc:
            raise AiUnavailable("The assistant budget cannot be checked right now.") from exc
        limit, upgrade = await self.allowance(user)
        if used >= limit and upgrade.recharge <= 0:
            metrics.increment("ai.guard.budget_exceeded")
            raise AiBudgetExceeded("You reached today's assistant budget; it resets tomorrow.")

    @asynccontextmanager
    async def slot(self, user: UUID) -> AsyncIterator[None]:
        with self._lock:
            if self._active.get(user, 0) >= PER_USER_CONCURRENCY or self._global >= GLOBAL_CONCURRENCY:
                metrics.increment("ai.guard.concurrency")
                raise AiRateLimited("An answer is already in progress; wait for it to finish.")
            self._active[user] = self._active.get(user, 0) + 1
            self._global += 1
        try:
            yield
        finally:
            with self._lock:
                self._active[user] -= 1
                if not self._active[user]:
                    del self._active[user]
                self._global -= 1

    async def record(self, user: UUID, tokens_in: int, tokens_out: int, tool_calls: int) -> None:
        before = None
        if self.perks is not None and tokens_in + tokens_out > 0:
            try:
                before = await self.used_today(user)
            except Exception:
                before = None
        values = {"tokens_in": tokens_in, "tokens_out": tokens_out, "requests": 1, "tool_calls": tool_calls}
        statement = insert(UsageDaily).values(user_id=user, day=self.today(), **values)
        statement = statement.on_conflict_do_update(
            index_elements=[UsageDaily.user_id, UsageDaily.day],
            set_={k: getattr(UsageDaily, k) + getattr(statement.excluded, k) for k in values},
        )
        try:
            async with self.database.unit_of_work() as uow:
                await uow.session.execute(statement)
        except Exception:
            metrics.increment("ai.usage.record_failed")
        metrics.increment("ai.tokens.in", tokens_in)
        metrics.increment("ai.tokens.out", tokens_out)
        if before is not None and self.perks is not None:
            # issue 173: what goes past the day's allowance is taken from the member's recharges
            limit, _ = await self.allowance(user)
            beyond = max(0, before + tokens_in + tokens_out - limit) - max(0, before - limit)
            if beyond:
                try:
                    await self.perks.spend(user, beyond)
                except Exception:
                    metrics.increment("ai.perks.spend_failed")

    async def usage(self, days: int = 30) -> list[dict[str, int | str]]:
        """Aggregates per day (no user ids, no content) for the admin usage view."""
        from sqlalchemy import func

        since = date.fromordinal(self.today().toordinal() - max(1, days) + 1)
        async with self.database.session() as session:
            rows = await session.execute(
                select(
                    UsageDaily.day,
                    func.count(UsageDaily.user_id),
                    func.sum(UsageDaily.tokens_in),
                    func.sum(UsageDaily.tokens_out),
                    func.sum(UsageDaily.requests),
                    func.sum(UsageDaily.tool_calls),
                )
                .where(UsageDaily.day >= since)
                .group_by(UsageDaily.day)
                .order_by(UsageDaily.day)
            )
            return [
                {
                    "day": day.isoformat(),
                    "users": int(users),
                    "tokens_in": int(tin or 0),
                    "tokens_out": int(tout or 0),
                    "requests": int(req or 0),
                    "tool_calls": int(calls or 0),
                }
                for day, users, tin, tout, req, calls in rows.all()
            ]
