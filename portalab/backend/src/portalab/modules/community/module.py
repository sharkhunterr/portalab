"""Community module facade (spec 012, slice A): members directory, visibility-correct profiles assembled
from registered sections, the activity feed projected from events, discovery shelves and member search,
and community events for the Calendar. A composition layer — it owns no engine (progression, leaderboards,
quests and funding stay with 013/015)."""

from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.community import (
    SectionRegistry,
    ShelfRegistry,
    default_sections,
    default_shelves,
)
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.content import CalendarSourceRegistry, default_calendar_sources
from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.capabilities.search import SearchRegistry, default_search
from portalab.capabilities.visibility import PREFERENCE_CAPABILITY
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock
from portalab.core.visibility_port import OwnerOnlyVisibility, VisibilityFilter
from portalab.modules.community import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.community.discovery.providers import MemberSearchProvider
from portalab.modules.community.discovery.shelves import register_builtin_shelves
from portalab.modules.community.events.service import CommunityEvents
from portalab.modules.community.events.types import register_event_types
from portalab.modules.community.feed.projector import CONSUMER, FeedProjector
from portalab.modules.community.feed.service import FeedService
from portalab.modules.community.integrations import ACTIVITY_WIDGET, ActivityWidget
from portalab.modules.community.leaderboards.view import LeaderboardsView
from portalab.modules.community.members.service import Members
from portalab.modules.community.models import FeedEntry
from portalab.modules.community.observability import log, metrics
from portalab.modules.community.preferences import CLASSES, CommunityPreferences
from portalab.modules.community.privacy.participant import CommunityParticipant
from portalab.modules.community.profiles.assembler import ProfileAssembler
from portalab.modules.community.profiles.builtin import register_builtin_sections
from portalab.modules.community.settings import SETTINGS, CommunityConfig

OWNER = "module:community"
INSTANCE = "community"


class CommunityModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        visibility: VisibilityFilter | None = None,
        event_types: EventTypeRegistry = default_event_types,
        consumers: ConsumerRegistry = default_consumers,
        sections: SectionRegistry = default_sections,
        shelves: ShelfRegistry = default_shelves,
        widgets: WidgetRegistry = default_widgets,
        search: SearchRegistry = default_search,
        calendar_sources: CalendarSourceRegistry = default_calendar_sources,
        observables: ObservableRegistry = default_observables,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.visibility = visibility or OwnerOnlyVisibility()
        self.event_types = event_types
        self.consumers = consumers
        self.sections = sections
        self.shelves = shelves
        self.widgets = widgets
        self.search = search
        self.calendar_sources = calendar_sources
        self.observables = observables
        self.config = CommunityConfig()
        self.members = Members(capabilities, self.visibility)
        self.feed = FeedService(database, self.visibility, self.display_name, clock=clock)
        self.projector = FeedProjector(
            database, event_types, self.visibility, lambda: self.config, clock=clock
        )
        self.profiles = ProfileAssembler(sections, self.visibility, authorizer)
        self.leaderboards = LeaderboardsView(capabilities, self.display_name)
        self.events = CommunityEvents(database, audit, events, authorizer, capabilities, clock=clock)

    async def display_name(self, user: UUID) -> str | None:
        directory = self.members.directory()
        summary = await directory.get_user_summary(user) if directory else None
        return summary.display_name if summary and not summary.anonymized else None

    def register(self) -> None:
        register_event_types(self.event_types)
        if self.consumers.get(CONSUMER) is None:
            self.consumers.register(self.projector.consumer())
        register_builtin_sections(self.sections, self.capabilities, self.feed, self.display_name)
        register_builtin_shelves(self.shelves, self.members, self.feed)
        if self.search.provider("member") is None:
            self.search.register(MemberSearchProvider(self.members, self.authorizer), owner=OWNER)
        if self.calendar_sources.get(self.events.kind) is None:
            self.calendar_sources.register(self.events, owner=OWNER)
        if self.widgets.get(ACTIVITY_WIDGET.key) is None:
            self.widgets.register(ACTIVITY_WIDGET, ActivityWidget(self.feed, self.clock), owner=OWNER)
        participant = CommunityParticipant(self.database)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == INSTANCE for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref=INSTANCE, owner=OWNER)
        if not any(
            p.instance_ref == INSTANCE for p in self.capabilities.system_providers(PREFERENCE_CAPABILITY)
        ):
            self.capabilities.provide(
                PREFERENCE_CAPABILITY,
                CommunityPreferences(self.database, clock=self.clock),
                instance_ref=INSTANCE,
                owner=OWNER,
                metadata={"datum_classes": list(CLASSES)},
            )
        default_retention_targets.register(
            RetentionTarget(
                "community.feed",
                "community.feed_entries",
                "activity",
                "occurred_at",
                "delete",
                OWNER,
                window=lambda: timedelta(days=max(1, self.config.feed_retention_days)),
            )
        )
        self.observables.declare(
            ObservedComponent(
                "community",
                OWNER,
                label="Community",
                functional_checks=(Check("feed", self.probe),),
                metrics=("community.feed.projected", "community.section.failed"),
            )
        )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def purge() -> None:
            await self.feed.purge(self.config.feed_retention_days)

        return [
            self.start,
            register_periodic(jobs, self.database, "community.purge", timedelta(hours=6), purge, owner=OWNER),
        ]

    async def start(self) -> None:
        await self.refresh_config()

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("community configuration not refreshed")

    async def probe(self) -> CheckResult:
        async with self.database.session() as session:
            entries = int(await session.scalar(select(func.count()).select_from(FeedEntry)) or 0)
        snapshot = metrics.snapshot()
        facts = {
            "feed_entries": entries,
            "section_failures": int(snapshot.get("community.section.failed", 0)),
        }
        return CheckResult("ok", "community surfaces respond", facts)
