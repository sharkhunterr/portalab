"""``CalendarAggregator`` (T025; R11, R12): fans out to every registered ``CalendarSource`` in parallel with
a per-source timeout. Permission is applied **at the source** (and a source may declare a
``required_permission`` checked first); one slow or failing source only degrades its own
``source_state``; the calendar owns no item and invents no deadline."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from portalab.capabilities.content import CalendarItem, CalendarSourceRegistry
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.errors import ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.calendar.settings import CalendarConfig


class RangeTooLarge(ValidationFailed):
    default_code = "calendar.range_too_large"
    default_title = "This date range is too large"


@dataclass(frozen=True, slots=True)
class CalendarView:
    items: list[CalendarItem]
    source_states: dict[str, str]
    as_of: datetime


class CalendarAggregator:
    def __init__(
        self,
        sources: CalendarSourceRegistry,
        authorizer: Authorizer,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.sources = sources
        self.authorizer = authorizer
        self.config = config  # callable → CalendarConfig
        self.clock = clock

    async def _allowed(self, viewer: Principal, permission: str | None) -> bool:
        if not permission:
            return True
        try:
            return await self.authorizer.is_allowed(viewer, permission)
        except Exception:
            return False

    async def view(
        self,
        viewer: Principal,
        start: datetime,
        end: datetime,
        ctx: LocaleContext,
        *,
        types: set[str] | None = None,
        kinds: set[str] | None = None,
    ) -> CalendarView:
        config: CalendarConfig = self.config()
        if end <= start:
            raise ValidationFailed("The end of the range is before its start.", code="calendar.invalid_range")
        if end - start > timedelta(days=max(1, config.max_range_days)):
            raise RangeTooLarge(f"Ask for at most {config.max_range_days} days at once.")
        timeout = max(0.1, config.source_timeout_ms / 1000)
        states: dict[str, str] = {}
        tasks: dict[str, Any] = {}
        for source in self.sources.all():
            if kinds and source.kind not in kinds:
                continue
            if not await self._allowed(viewer, getattr(source, "required_permission", None)):
                continue  # the viewer may not see this source at all: it is simply absent
            tasks[source.kind] = asyncio.create_task(
                asyncio.wait_for(source.items(start, end, viewer, ctx), timeout)
            )
        items: list[CalendarItem] = []
        for kind, task in tasks.items():
            try:
                result = await task
            except Exception:
                states[kind] = "unavailable"
                continue
            states[kind] = result.state
            items.extend(i for i in result.items if not types or i.type in types)
        items.sort(key=lambda item: (when(item, start), item.title))
        return CalendarView(items, states, utc_now(self.clock))


def when(item: CalendarItem, default: datetime) -> datetime:
    """Sort instant of an item: its start, or the beginning of its all-day date (UTC)."""
    if item.starts_at is not None:
        return item.starts_at
    if item.date is not None:
        return datetime.combine(item.date, datetime.min.time(), tzinfo=default.tzinfo)
    return default
