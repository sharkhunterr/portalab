""" "Since Last Login" (T028; R10): aggregates ``ChangeSummaryProvider.changes_since`` of the registered
domains in parallel (each under a time budget, permission and privacy applied **at the source**), ranks by
priority then recency and caps the list. The boundary is ``max(last_summary_seen_at, now - lookback)``
and only advances when the user acknowledges (``seen``) — two sessions never lose each other's items."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.dashboard import ChangeItem, ChangeSummaryProvider, WidgetRegistry
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import NotFound
from portalab.core.time import Clock, utc_now
from portalab.modules.dashboard.models import UserDashboard
from portalab.modules.dashboard.observability import log, metric_part, metrics
from portalab.modules.dashboard.settings import DashboardConfig

PROVIDER_BUDGET = 3.0


@dataclass
class Summary:
    since: datetime
    items: list[ChangeItem] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)  # kinds that could not answer


class SinceLastLogin:
    def __init__(
        self,
        database: Database,
        registry: WidgetRegistry,
        config: Callable[[], DashboardConfig],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.registry = registry
        self.config = config
        self.clock = clock

    def _user(self, principal: Principal) -> Any:
        user = principal.acting_for or principal.user_id
        if user is None:
            raise NotFound()
        return user

    async def boundary(self, principal: Principal) -> datetime:
        now = utc_now(self.clock)
        floor = now - timedelta(days=max(1, self.config().lookback_days))
        async with self.database.session() as session:
            board = await session.get(UserDashboard, self._user(principal))
        seen = board.last_summary_seen_at if board else None
        return max(seen, floor) if seen else floor

    async def summary(self, principal: Principal, ctx: LocaleContext) -> Summary:
        config = self.config()
        since = await self.boundary(principal)
        limit = max(1, config.max_items)
        wanted = set(config.summary_types)
        providers: Sequence[ChangeSummaryProvider] = [
            p for p in self.registry.summaries() if not wanted or p.kind in wanted
        ]
        results = await asyncio.gather(
            *(self._one(provider, principal, since, limit, ctx) for provider in providers)
        )
        out = Summary(since=since)
        for provider, result in zip(providers, results, strict=True):
            if result is None:
                out.unavailable.append(provider.kind)
                continue
            out.items.extend(item for item in result if item.occurred_at > since)
        out.items.sort(key=lambda item: (-item.priority, -item.occurred_at.timestamp()))
        out.items = out.items[:limit]
        return out

    async def _one(
        self,
        provider: ChangeSummaryProvider,
        principal: Principal,
        since: datetime,
        limit: int,
        ctx: LocaleContext,
    ) -> Sequence[ChangeItem] | None:
        try:
            return await asyncio.wait_for(
                provider.changes_since(principal, since, limit, ctx), PROVIDER_BUDGET
            )
        except Exception:
            log.warning("summary provider failed", extra={"kind": provider.kind})
            metrics.increment(f"dashboard.summary.{metric_part(provider.kind)}.failures")
            return None

    async def seen(self, principal: Principal, until: datetime | None = None) -> datetime:
        """Advance the boundary (never backwards; never beyond now)."""
        now = utc_now(self.clock)
        at = min(until or now, now)
        user = self._user(principal)
        async with self.database.unit_of_work() as uow:
            board = await uow.session.get(UserDashboard, user, with_for_update=True)
            if board is None:
                await uow.session.execute(
                    insert(UserDashboard)
                    .values(user_id=user, layout_version=0, updated_at=now, last_summary_seen_at=at)
                    .on_conflict_do_nothing(index_elements=["user_id"])
                )
                return at
            if board.last_summary_seen_at is None or at > board.last_summary_seen_at:
                board.last_summary_seen_at = at
            return board.last_summary_seen_at or at
