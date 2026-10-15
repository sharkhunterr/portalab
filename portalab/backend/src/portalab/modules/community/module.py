"""Community module facade (spec 012, slice A): members directory, visibility-correct profiles assembled
from registered sections, the activity feed projected from events, discovery shelves and member search,
and community events for the Calendar. A composition layer — it owns no engine (progression, leaderboards,
quests and funding stay with 013/015)."""

import time
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
from portalab.capabilities.navigation.attention import ATTENTION
from portalab.capabilities.notifications import declare_category, default_categories
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
from portalab.capabilities.support import PROPOSALS
from portalab.capabilities.themes import COSMETICS
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
from portalab.modules.community.achievements.view import AchievementsView
from portalab.modules.community.attention import ModerationAttention
from portalab.modules.community.discovery.providers import MemberSearchProvider
from portalab.modules.community.discovery.shelves import register_builtin_shelves
from portalab.modules.community.events.service import CommunityEvents
from portalab.modules.community.events.types import register_event_types
from portalab.modules.community.feed.projector import CONSUMER, FeedProjector
from portalab.modules.community.feed.service import FeedService
from portalab.modules.community.integrations import (
    ACTIVITY_WIDGET,
    PROJECTS_WIDGET,
    ActivityWidget,
    ProjectsWidget,
)
from portalab.modules.community.leaderboards.view import LeaderboardsView
from portalab.modules.community.members.service import Members
from portalab.modules.community.models import FeedEntry
from portalab.modules.community.observability import log, metrics
from portalab.modules.community.participation.service import Participations
from portalab.modules.community.preferences import CLASSES, CommunityPreferences
from portalab.modules.community.privacy.participant import CommunityParticipant
from portalab.modules.community.profiles.assembler import ProfileAssembler
from portalab.modules.community.profiles.builtin import register_builtin_sections
from portalab.modules.community.proposals.lifecycle import CATEGORY, StatusNotifier
from portalab.modules.community.proposals.lifecycle import CONSUMER as STATUS_CONSUMER
from portalab.modules.community.proposals.service import ProposalCreatorAdapter, Proposals
from portalab.modules.community.proposals.types import register_slice_d_types
from portalab.modules.community.quests.view import QuestsView
from portalab.modules.community.settings import SETTINGS, CommunityConfig
from portalab.modules.community.votes.service import Votes

OWNER = "module:community"
INSTANCE = "community"


LOOK_SECONDS = 60.0  # #127: how long a member's worn frame and name style are kept


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
        self._looks: dict[UUID, tuple[float, dict[str, Any]]] = {}
        self.leaderboards = LeaderboardsView(capabilities, self.display_name, self.look_of)
        self.achievements = AchievementsView(capabilities, self.visibility)
        self.quests = QuestsView(capabilities)
        config = lambda: self.config  # noqa: E731
        self.proposals = Proposals(database, events, audit, capabilities, authorizer, config, clock=clock)
        self.votes = Votes(database, events, self.proposals, clock=clock)
        self.participations = Participations(database, events, audit, self.proposals, config, clock=clock)
        self.status_notifier = StatusNotifier(database, capabilities)
        self.events = CommunityEvents(database, audit, events, authorizer, capabilities, clock=clock)

    async def display_name(self, user: UUID) -> str | None:
        directory = self.members.directory()
        summary = await directory.get_user_summary(user) if directory else None
        return summary.display_name if summary and not summary.anonymized else None

    def register(self) -> None:
        if not any(p.instance_ref == "community" for p in self.capabilities.system_providers(ATTENTION)):
            # #98: what waits for an administrator here — a badge on the navigation
            self.capabilities.provide(
                ATTENTION,
                ModerationAttention(self.database, self.authorizer),
                instance_ref="community",
                owner=OWNER,
            )
        register_event_types(self.event_types)
        register_slice_d_types(self.event_types)
        if self.consumers.get(CONSUMER) is None:
            self.consumers.register(self.projector.consumer())
        if self.consumers.get(STATUS_CONSUMER) is None:
            self.consumers.register(self.status_notifier.consumer())
        if not self.capabilities.system_providers(PROPOSALS):
            self.capabilities.provide(
                PROPOSALS, ProposalCreatorAdapter(self.proposals), instance_ref=INSTANCE, owner=OWNER
            )
        if default_categories.get(CATEGORY) is None:
            declare_category(CATEGORY, OWNER, "community:category.project")
        register_builtin_sections(
            self.sections, self.capabilities, self.feed, self.display_name, self.proposals
        )
        register_builtin_shelves(self.shelves, self.members, self.feed, self.proposals)
        if self.search.provider("member") is None:
            self.search.register(MemberSearchProvider(self.members, self.authorizer), owner=OWNER)
        if self.calendar_sources.get(self.events.kind) is None:
            self.calendar_sources.register(self.events, owner=OWNER)
        if self.widgets.get(ACTIVITY_WIDGET.key) is None:
            activity = ActivityWidget(self.feed, self.clock, self.look_of)
            self.widgets.register(ACTIVITY_WIDGET, activity, owner=OWNER)
        if self.widgets.get(PROJECTS_WIDGET.key) is None:
            self.widgets.register(
                PROJECTS_WIDGET, ProjectsWidget(self.proposals, self.votes, self.clock), owner=OWNER
            )
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

    async def look_of(self, member: UUID) -> dict[str, Any]:
        """#127: the avatar frame and the name's style a member wears, shown beside them across the
        community (the leaderboards, the feed, the directory) — kept a minute (lists ask for many)."""
        now = time.monotonic()
        kept = self._looks.get(member)
        if kept is not None and now - kept[0] < LOOK_SECONDS:
            return kept[1]
        worn = await self.looks_of(member)
        look = {"frame": worn.get("frame"), "name": worn.get("name")}
        if len(self._looks) >= 2000:
            self._looks.clear()
        self._looks[member] = (now, look)
        return look

    async def looks_of(self, member: UUID) -> dict[str, Any]:
        """027: what the member wears on their profile (read from the Marketplace's cosmetics)."""
        try:
            providers = self.capabilities.system_providers(COSMETICS)
        except Exception:
            return {}
        if not providers:
            return {}
        try:
            return dict(await providers[0].provider.equipped(member))
        except Exception:
            return {}
