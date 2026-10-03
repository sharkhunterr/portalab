"""PluginGuard (T022; R3): every plugin-supplied callable runs behind a guard — a timeout
(``plugins.hookTimeoutSeconds``), exception capture (the failing request or handler fails alone, with a
sanitized error type, never a stack trace or a secret), counters per 10-minute window in
``plugins.error_stats``, a per-plugin rate limit, and **quarantine** once ``plugins.errorThreshold`` errors
accumulate (contributions removed, data intact, Admin notified)."""

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.core.db import Database
from portalab.core.errors import PortalError
from portalab.core.time import Clock, utc_now
from portalab.modules.plugins.models import ErrorStat
from portalab.modules.plugins.observability import log, metrics

WINDOW = timedelta(minutes=10)


class PluginHookFailed(PortalError):
    status = 502
    default_code = "plugin.hook_failed"
    default_title = "A plugin failed"


class PluginRateLimited(PortalError):
    status = 429
    default_code = "plugin.rate_limited"
    default_title = "Too many plugin requests"


def window_start(at: datetime) -> datetime:
    return at.replace(minute=at.minute - at.minute % 10, second=0, microsecond=0)


class PluginGuard:
    def __init__(
        self,
        database: Database,
        config: Callable[[], Any],
        *,
        clock: Clock | None = None,
        rate_per_minute: int = 120,
    ) -> None:
        self.database = database
        self.config = config
        self.clock = clock
        self.rate_per_minute = rate_per_minute
        self.on_threshold: Callable[[str, str], Awaitable[None]] | None = None
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    def check_rate(self, plugin: str) -> None:
        now = time.monotonic()
        calls = self._calls[plugin]
        while calls and now - calls[0] > 60:
            calls.popleft()
        if len(calls) >= self.rate_per_minute:
            raise PluginRateLimited("This plugin is receiving too many requests.")
        calls.append(now)

    async def record(self, plugin: str, kind: str, error: BaseException | str) -> int:
        at = utc_now(self.clock)
        sample = error if isinstance(error, str) else type(error).__name__
        start = window_start(at)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(ErrorStat)
                .values(plugin_key=plugin, window_start=start, kind=kind, count=1, last_sample=sample[:300])
                .on_conflict_do_update(
                    index_elements=[ErrorStat.plugin_key, ErrorStat.window_start, ErrorStat.kind],
                    set_={"count": ErrorStat.count + 1, "last_sample": sample[:300]},
                )
            )
            total = int(
                await uow.session.scalar(
                    select(func.coalesce(func.sum(ErrorStat.count), 0)).where(
                        ErrorStat.plugin_key == plugin,
                        ErrorStat.window_start >= start,
                    )
                )
                or 0
            )
        metrics.increment(f"plugins.errors.{kind}")
        log.warning(
            "plugin hook failed", extra={"fields": {"plugin": plugin, "kind": kind, "error": sample[:80]}}
        )
        if total >= max(1, int(self.config().error_threshold)) and self.on_threshold is not None:
            await self.on_threshold(plugin, f"{total} errors in 10 minutes ({kind}: {sample[:80]})")
        return total

    async def run(
        self, plugin: str, kind: str, call: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
    ) -> Any:
        try:
            return await asyncio.wait_for(
                call(*args, **kwargs), timeout=float(self.config().hook_timeout_seconds)
            )
        except PortalError as error:
            if error.status < 500:  # an expected refusal from the plugin (validation, not found…)
                raise
            await self.record(plugin, kind, error)
            raise PluginHookFailed("The plugin could not complete this request.") from None
        except Exception as error:
            await self.record(plugin, kind, "timeout" if isinstance(error, TimeoutError) else error)
            raise PluginHookFailed("The plugin could not complete this request.") from None

    def wrap(
        self, plugin: str, kind: str, call: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        async def guarded(*args: Any, **kwargs: Any) -> Any:
            return await self.run(plugin, kind, call, *args, **kwargs)

        return guarded

    async def stats(self, plugin: str) -> list[ErrorStat]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(ErrorStat)
                        .where(ErrorStat.plugin_key == plugin)
                        .order_by(ErrorStat.window_start.desc())
                    )
                ).scalars()
            )


class GuardedWidget:
    def __init__(self, guard: PluginGuard, plugin: str, provider: Any) -> None:
        self._load = guard.wrap(plugin, "widget", provider.load)

    async def load(self, principal: Any, config: Any, ctx: Any) -> Any:
        return await self._load(principal, config, ctx)


class GuardedSearch:
    def __init__(self, guard: PluginGuard, plugin: str, provider: Any) -> None:
        self.kind = provider.kind
        self.label_key = provider.label_key
        self.required_permission = provider.required_permission
        self._provider = provider
        self._search = guard.wrap(plugin, "hook", provider.search)
        self._hydrate = guard.wrap(plugin, "hook", provider.hydrate)

    def facets(self) -> Any:
        return self._provider.facets()

    async def search(self, query: Any, principal: Any, ctx: Any, *, limit: int, cursor: str | None) -> Any:
        return await self._search(query, principal, ctx, limit=limit, cursor=cursor)

    async def hydrate(self, ids: Any, principal: Any) -> Any:
        return await self._hydrate(ids, principal)


class GuardedCalendar:
    def __init__(self, guard: PluginGuard, plugin: str, source: Any) -> None:
        self.kind = source.kind
        self.label_key = source.label_key
        self._items = guard.wrap(plugin, "hook", source.items)
        self._item = guard.wrap(plugin, "hook", source.item)

    async def items(self, start: Any, end: Any, viewer: Any, ctx: Any) -> Any:
        return await self._items(start, end, viewer, ctx)

    async def item(self, source_id: str, viewer: Any) -> Any:
        return await self._item(source_id, viewer)
