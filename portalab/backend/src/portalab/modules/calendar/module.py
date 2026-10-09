"""Calendar module facade (spec 011)."""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.content import CalendarSourceRegistry, default_calendar_sources
from portalab.capabilities.dashboard import (
    Refresh,
    Size,
    SizeLimits,
    WidgetDefinition,
    WidgetPayload,
    WidgetRegistry,
    default_widgets,
    with_styles,
)
from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.notifications import CategoryRegistry, declare_category, default_categories
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.privacy_participants import (
    ERASURE_CAPABILITY,
    EXPORT_CAPABILITY,
    ErasureMode,
    ExportRecord,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.registry import JobRegistry
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.calendar import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.calendar import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.calendar.aggregator import CalendarAggregator
from portalab.modules.calendar.events import register_event_types
from portalab.modules.calendar.permissions import CALENDAR_READ
from portalab.modules.calendar.reminders import JOB, ReminderService
from portalab.modules.calendar.settings import SETTINGS, CalendarConfig

OWNER = "module:calendar"
log = get_logger("portalab.calendar")
UPCOMING = WidgetDefinition(
    key="calendar.upcoming",
    owner=OWNER,
    title_key="calendar:widget.upcoming.title",
    description_key="calendar:widget.upcoming.description",
    icon="calendar",
    required_permission=CALENDAR_READ,
    size=SizeLimits(default=Size(6, 3), min=Size(3, 2), max=Size(12, 6)),
    refresh=Refresh(),
    stale_after_s=900,
    template="list",
    component_id="calendar.upcoming",  # 027 (#31): the list, or « flip » — the next date on flip digits
)
UPCOMING = with_styles(UPCOMING, "flip")


class UpcomingWidget:
    def __init__(self, aggregator: CalendarAggregator, clock: Clock | None = None) -> None:
        self.aggregator = aggregator
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        now = utc_now(self.clock)
        view = await self.aggregator.view(principal, now, now + timedelta(days=14), ctx)
        items = [
            {"title": i.title, "route": i.url_ref if i.url_ref and i.url_ref.startswith("/") else "/calendar",
             "meta": (i.starts_at.isoformat() if i.starts_at else str(i.date))}
            for i in view.items[:8]
        ]  # fmt: skip
        if not items:
            return WidgetPayload("no-data", as_of=now)
        if any(s != "ok" for s in view.source_states.values()):
            return WidgetPayload("partial", as_of=now, data={"items": items})
        return WidgetPayload("available", as_of=now, data={"items": items})


MONTH = WidgetDefinition(
    key="calendar.month",
    owner=OWNER,
    title_key="calendar:widget.month.title",
    description_key="calendar:widget.month.description",
    icon="calendar",
    required_permission=CALENDAR_READ,
    size=SizeLimits(default=Size(6, 6), min=Size(4, 5), max=Size(12, 8)),
    refresh=Refresh(),
    stale_after_s=900,
    component_id="calendar.month",
    config_schema={
        "type": "object",
        "properties": {"show": {"type": "string", "enum": ["all", "media", "events"]}},
        "additionalProperties": False,
    },
    config_defaults={"show": "all"},
)


class MonthWidget:
    """027: this month as a calendar grid (marks on the days with something) and what comes next —
    portal events, maintenance, news and media releases (films and episodes)."""

    def __init__(self, aggregator: CalendarAggregator, clock: Clock | None = None) -> None:
        self.aggregator = aggregator
        self.clock = clock

    async def load(
        self, principal: Principal, config: Mapping[str, Any], ctx: LocaleContext
    ) -> WidgetPayload:
        now = utc_now(self.clock)
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (first + timedelta(days=32)).replace(day=1) + timedelta(days=7)
        view = await self.aggregator.view(principal, first - timedelta(days=7), end, ctx)
        show = str(config.get("show") or "all")
        items = [
            i for i in view.items if show == "all" or (i.source_kind == "media_release") == (show == "media")
        ]
        zone = _zone(ctx.time_zone)
        today = now.astimezone(zone).date()
        entries: list[dict[str, Any]] = []
        for item in items:
            start_day = item.date or (item.starts_at.astimezone(zone).date() if item.starts_at else None)
            if start_day is None:
                continue
            end_day = start_day
            if item.ends_at is not None and not item.date:
                # an end at midnight closes the previous day
                end_day = max(start_day, (item.ends_at.astimezone(zone) - timedelta(seconds=1)).date())
            entries.append(
                {
                    "title": item.title,
                    "kind": item.source_kind,
                    "category": item.category,
                    "status": item.status,
                    "time": None if item.all_day or item.starts_at is None else item.starts_at.isoformat(),
                    "route": item.url_ref if item.url_ref and item.url_ref.startswith("/") else "/calendar",
                    "date": start_day.isoformat(),
                    "end": end_day.isoformat(),
                }
            )
        entries.sort(key=lambda e: (e["date"], e["end"]))
        upcoming = [e for e in entries if e["end"] >= today.isoformat()][:6]
        data = {
            "month": first.date().isoformat(),
            "today": today.isoformat(),
            "entries": entries,
            "upcoming": upcoming,
        }
        if any(s != "ok" for s in view.source_states.values()):
            return WidgetPayload("partial", as_of=now, data=data)
        return WidgetPayload("available", as_of=now, data=data)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


class _Participant:
    def __init__(self, reminders: ReminderService) -> None:
        self.reminders = reminders

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        return [
            ExportRecord(
                "calendar.reminder",
                {"title": r.title, "remind_at": r.remind_at.isoformat(), "status": r.status},
            )
            for r in await self.reminders.mine(user_id)
        ]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        await self.reminders.erase(user_id)


class CalendarModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        sources: CalendarSourceRegistry = default_calendar_sources,
        event_types: EventTypeRegistry = default_event_types,
        widgets: WidgetRegistry = default_widgets,
        categories: CategoryRegistry = default_categories,
        observables: ObservableRegistry = default_observables,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self.config = CalendarConfig()
        self.sources = sources
        self.event_types = event_types
        self.widgets = widgets
        self.categories = categories
        self.observables = observables
        self.aggregator = CalendarAggregator(sources, authorizer, lambda: self.config, clock=clock)
        self.reminders = ReminderService(
            database, events, capabilities, sources, lambda: self.config, clock=clock
        )

    def register(self) -> None:
        register_event_types(self.event_types)
        participant = _Participant(self.reminders)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == "calendar" for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref="calendar", owner=OWNER)
        if self.widgets.get(UPCOMING.key) is None:
            self.widgets.register(UPCOMING, UpcomingWidget(self.aggregator, self.clock), owner=OWNER)
        if self.widgets.get(MONTH.key) is None:
            self.widgets.register(MONTH, MonthWidget(self.aggregator, self.clock), owner=OWNER)
        if self.categories.get("calendar.reminder") is None:
            declare_category(
                "calendar.reminder", OWNER, "calendar:category.reminder", registry=self.categories
            )
        self.observables.declare(
            ObservedComponent(
                "calendar", OWNER, label="Calendar", functional_checks=(Check("sources", self.probe),)
            )
        )

    async def probe(self) -> CheckResult:
        """Every calendar source answers within its timeout for a system viewer."""
        now = utc_now(self.clock)
        view = await self.aggregator.view(
            Principal(channel="system"), now, now + timedelta(days=1), LocaleContext()
        )
        failing = sorted(kind for kind, state in view.source_states.items() if state != "ok")
        if failing:
            return CheckResult("degraded", "some calendar sources do not answer", {"failing": failing})
        return CheckResult("ok", "calendar sources answer", {"sources": len(view.source_states)})

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def fire(payload: dict[str, Any]) -> None:
            await self.reminders.fire(payload)

        jobs.register(
            JOB, fire, idempotency="reminder status checked; notification deduplicated", owner=OWNER
        )
        return [self.refresh_config]

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("calendar configuration not refreshed")
