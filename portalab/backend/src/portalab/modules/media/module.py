"""Media module facade (spec 024)."""

import contextlib
import os
from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.activity import CAPABILITY as ACTIVITY
from portalab.capabilities.ai import AIToolRegistry, default_ai_tools
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.content import CalendarSourceRegistry, default_calendar_sources
from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.i18n import RESOLVER as I18N_RESOLVER
from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.media import ACTIVITY_HISTORY, DIGEST, LIBRARY, MENTIONS, METADATA, REQUESTS
from portalab.capabilities.media_core import (
    CARD_SOURCES,
    CATALOG,
    GAME_SOURCES,
    HISTORY,
    QUOTA,
    RADIO_CREDITS,
    RECOMMENDATIONS,
    RESCUES,
    DetailBlockRegistry,
    MediaTypeRegistry,
    default_detail_blocks,
    default_media_types,
    register_baseline,
)
from portalab.capabilities.navigation.attention import ATTENTION
from portalab.capabilities.notifications import NOTIFY, CategoryRegistry, declare_category, default_categories
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.record_sink import SinkRegistry, default_sinks
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.capabilities.search import SearchRegistry, default_search
from portalab.capabilities.service_signals import default_signals
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.queue import enqueue
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock, utc_now
from portalab.core.visibility_port import VisibilityFilter
from portalab.modules.media import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.media import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.media.attention import FeedAttention, RequestsAttention
from portalab.modules.media.availability.service import AvailabilityService
from portalab.modules.media.books.service import BookService
from portalab.modules.media.cards import MediaCardSources
from portalab.modules.media.catalog import CatalogPort, CatalogQuery
from portalab.modules.media.cleanup import CleanupService
from portalab.modules.media.discovery.shelves import Discovery
from portalab.modules.media.events import register_event_types
from portalab.modules.media.feed import Feed
from portalab.modules.media.fields.resolver import FieldResolver
from portalab.modules.media.games import MediaGameSources
from portalab.modules.media.history.projection import HistoryProjection
from portalab.modules.media.identity.resolver import IdentityResolver
from portalab.modules.media.images.service import JOB as IMAGE_JOB
from portalab.modules.media.images.service import ImageService
from portalab.modules.media.insights.aggregate import JOB as AGGREGATE_JOB
from portalab.modules.media.insights.aggregate import ActivityAggregator
from portalab.modules.media.insights.calendar_source import MediaReleaseCalendarSource
from portalab.modules.media.insights.deep import DeepInsights
from portalab.modules.media.insights.digest import LibraryDigest
from portalab.modules.media.insights.enrich import JOB as ENRICH_JOB
from portalab.modules.media.insights.enrich import MetadataEnricher
from portalab.modules.media.insights.ingest import JOB as ACTIVITY_JOB
from portalab.modules.media.insights.ingest import ActivityIngestor
from portalab.modules.media.insights.portal import PortalActivity
from portalab.modules.media.insights.rewards import HistoryRewards
from portalab.modules.media.insights.stats import InsightsQuery
from portalab.modules.media.insights.upcoming import Upcoming
from portalab.modules.media.links.accounts import AccountMatching
from portalab.modules.media.links.service import UserLinkService
from portalab.modules.media.mentions import LibraryMentions
from portalab.modules.media.models import MatchCandidate, PlaybackSession, SourceItem
from portalab.modules.media.observability import log, metrics
from portalab.modules.media.participant import MediaParticipant
from portalab.modules.media.people import People, Profiles
from portalab.modules.media.playback.poller import JOB as POLL_JOB
from portalab.modules.media.playback.poller import PlaybackPoller
from portalab.modules.media.player.service import PlayerService
from portalab.modules.media.providers.ai_tools import MediaAiTools
from portalab.modules.media.providers.insight_widgets import (
    DOWNLOADS_WIDGET,
    LEAVING_WIDGET,
    LIVING_WALL,
    MY_SOON,
    NEXT_RELEASES,
    ON_THIS_DAY,
    POSTER_WALL,
    RECENT_RELEASES,
    RECENTLY_ADDED,
    RECENTLY_REQUESTED,
    SERVER_PLAYING,
    DownloadsWidget,
    LeavingWidget,
    LivingWallWidget,
    MySoonWidget,
    NextReleasesWidget,
    OnThisDayWidget,
    PosterWallWidget,
    RecentlyAddedWidget,
    RecentlyRequestedWidget,
    ServerPlayingWidget,
    ShuffleWidget,
    StatsWidget,
    TopWidget,
    UpcomingWidget,
)
from portalab.modules.media.providers.insight_widgets import SHUFFLE as SHUFFLE_WIDGET
from portalab.modules.media.providers.insight_widgets import STATS as STATS_WIDGET
from portalab.modules.media.providers.insight_widgets import TOP as TOP_WIDGET
from portalab.modules.media.providers.insight_widgets import UPCOMING as UPCOMING_WIDGET
from portalab.modules.media.providers.ports import HistoryReader, MediaActivityAttributes
from portalab.modules.media.providers.search import (
    ACTIONS,
    MediaResolver,
    MediaSearchProvider,
    PeopleSearchProvider,
    RequestableSearchProvider,
)
from portalab.modules.media.providers.summary import MediaChanges
from portalab.modules.media.providers.taste_widgets import FOR_YOU, TASTE, ForYouWidget, TasteWidget
from portalab.modules.media.providers.widgets import (
    CONTINUE,
    RECENT,
    ContinueWidget,
    RecentWidget,
    RequestsWidget,
)
from portalab.modules.media.providers.widgets import (
    REQUESTS as REQUESTS_WIDGET,
)
from portalab.modules.media.radio import RADIO_WIDGET, RadioService, RadioWidget
from portalab.modules.media.requests.discovery import RequestableCatalog
from portalab.modules.media.requests.insights import RequestInsights
from portalab.modules.media.requests.journey import RequestJourney
from portalab.modules.media.requests.moderation import RequestModeration
from portalab.modules.media.requests.quota import RequestQuota
from portalab.modules.media.requests.service import Requests, RequestSink
from portalab.modules.media.requests.watched import LeavingWatched, RequestWatched
from portalab.modules.media.sections.service import Sections
from portalab.modules.media.settings import (
    PRIORITY_FIELDS,
    SETTINGS,
    MediaConfig,
    priority_key,
    threshold_key,
)
from portalab.modules.media.signals import register_media_signals
from portalab.modules.media.sink.library import CatalogWriter, LibrarySink
from portalab.modules.media.taste.service import TasteRecommender, TasteService

OWNER = "module:media"
CATEGORIES = (
    ("media.available", "media:category.available", ("portal", "email")),
    ("media.request_updated", "media:category.request_updated", ("portal",)),
    ("media.new_in_library", "media:category.new_in_library", ("portal",)),
    ("media.feed", "media:category.feed", ("portal",)),  # #299: what arrived in « Mon fil »
)


class MediaModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        blobs: BlobStore | None = None,
        visibility: VisibilityFilter | None = None,
        clock: Clock | None = None,
        event_types: EventTypeRegistry = default_event_types,
        consumers: ConsumerRegistry = default_consumers,
        sinks: SinkRegistry = default_sinks,
        types: MediaTypeRegistry = default_media_types,
        blocks: DetailBlockRegistry = default_detail_blocks,
        widgets: WidgetRegistry = default_widgets,
        calendar: CalendarSourceRegistry = default_calendar_sources,
        search: SearchRegistry = default_search,
        categories: CategoryRegistry = default_categories,
        observables: ObservableRegistry = default_observables,
        player_key: bytes | None = None,
        assistant_tools: AIToolRegistry = default_ai_tools,
    ) -> None:
        self.assistant_tools = assistant_tools  # issue 171: the assistant's media tools
        self.database = database
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.config = MediaConfig()
        self.event_types = event_types
        self.consumers = consumers
        self.sinks = sinks
        self.types = types
        self.blocks = blocks
        self.widgets = widgets
        self.search = search
        self.categories = categories
        self.observables = observables
        self.images = ImageService(database, capabilities, blobs, clock=clock)
        self.identity = IdentityResolver(lambda: self.config.match_auto_threshold)
        self.fields = FieldResolver(self.priorities)
        self.writer = CatalogWriter(
            database, events, self.identity, self.fields, clock=clock, on_image=self.images.schedule
        )
        self.library = LibrarySink(self.writer, types, clock=clock)
        self.links = UserLinkService(database, capabilities, clock=clock)
        self.accounts = AccountMatching(database, capabilities, clock=clock)
        self.poller = PlaybackPoller(
            database,
            events,
            capabilities,
            self.links,
            lambda: self.config,
            self.threshold,
            credits=self.credits_start,  # #101: a play is finished at its end credits
            clock=clock,
        )
        self.history = HistoryProjection(database, events, clock=clock)
        # #94: a finished play the live watch missed (seen in a service's history) still counts
        self.history_rewards = HistoryRewards(
            database, events, self.threshold, credits=self.credits_start, clock=clock
        )
        self.quota = RequestQuota(database, lambda: self.config, clock=clock)
        self.requests = Requests(database, events, capabilities, self.quota, self.links, clock=clock)
        self.request_sink = RequestSink(self.requests)
        self.catalog = CatalogQuery(database, authorizer)
        self.catalog_port = CatalogPort(self.catalog)
        self.people = People(database)  # #92: the people behind the titles
        self.profiles = Profiles(capabilities)  # #92: what the services know of them
        self.availability = AvailabilityService(database, capabilities, clock=clock)
        self.sections = Sections(
            database,
            capabilities,
            authorizer,
            self.catalog,
            self.availability,
            blocks,
            visibility=visibility,
            clock=clock,
        )
        self.discovery = Discovery(database, capabilities, self.history, lambda: self.config, clock=clock)
        # issue 190: each member's taste, and the recommendations made from it (with their reasons)
        self.taste = TasteService(database, capabilities, clock=clock)
        self.feed = Feed(database, self.people, clock=clock)  # #299: « Mon fil »
        self.recommender = TasteRecommender(self.taste)
        self.history_reader = HistoryReader(database, visibility)
        # 027: Telemetra-style statistics, metadata enrichment and release calendars
        self.ingestor = ActivityIngestor(database, capabilities, clock=clock)
        self.aggregator = ActivityAggregator(database)
        self.enricher = MetadataEnricher(database, capabilities, self.language, blobs=blobs, clock=clock)
        self.insights = InsightsQuery(database, clock=clock)
        self.deep_insights = DeepInsights(database, clock=clock)  # 027: the statistics' tabs
        self.upcoming = Upcoming(database, capabilities, clock=clock)
        self.calendar = calendar
        self.request_insights = RequestInsights(
            database, capabilities, self.upcoming, clock=clock, enricher=self.enricher, visibility=visibility
        )
        self.journey = RequestJourney(  # 027: a title's request journey (media page)
            database, capabilities, self.catalog, self.request_insights, clock=clock
        )
        self.cleanup = CleanupService(database, capabilities, clock=clock)  # #57: Maintainerr's deletions
        # issue 168: the homelab's radio (SUB/WAVE); 184: free requests each day, then credits
        self.radio = RadioService(capabilities, database, lambda: self.config, clock=clock, events=events)
        self.requestable = RequestableCatalog(database, capabilities)  # #4: what one can ask for (Seerr)
        self.moderation = RequestModeration(self.requests)  # #4: administrators approve or decline
        self.ai_tools = MediaAiTools(  # issue 171: offered to the assistant, with a title's journey
            self.catalog,
            self.history_reader,
            self.discovery,
            self.journey,
            clock=clock,
            cleanup=self.cleanup,
            sections=self.sections,
        )
        # 027 (#2): the portal's player (its stream tickets are signed with a key of the portal's secret)
        self.player = PlayerService(
            database,
            capabilities,
            lambda: self.config,
            player_key or os.urandom(32),
            events=events,  # #103: a title cast to a TV is the member's event
            clock=clock,
        )
        # #20, #21: listening and reading in the portal (their tickets: another key of the same secret)
        self.books = BookService(
            database, events, capabilities, lambda: self.config, player_key or os.urandom(32), clock=clock
        )

    # --- configuration ---------------------------------------------------------------------------------
    def _config_reader(self) -> Any | None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def priorities(self, kind: str) -> dict[str, list[str]]:
        reader = self._config_reader()
        if reader is None:
            return {}
        out: dict[str, list[str]] = {}
        for name in PRIORITY_FIELDS:
            try:
                value = (await reader.get(priority_key(kind, name))).value
            except Exception:  # noqa: S112 — undeclared kind/field: no preference
                continue
            if isinstance(value, list) and value:
                out[name] = [str(v) for v in value]
        return out

    async def language(self) -> str:
        """The portal's default language (metadata is fetched in it)."""
        reader = self._config_reader()
        if reader is None:
            return "en"
        try:
            value = (await reader.get("i18n.defaultLocale")).value
        except Exception:
            return "en"
        return str(value or "en")

    async def member_language(self, principal: Principal) -> str:
        """#4: the member's own language (what they read the portal in), else the portal's."""
        with contextlib.suppress(Exception):
            providers = self.capabilities.system_providers(I18N_RESOLVER)
            if providers and principal.user_id is not None:
                ctx = await providers[0].provider.for_user(principal.acting_for or principal.user_id)
                if isinstance(ctx, LocaleContext) and ctx.language:
                    return str(ctx.language)
        return await self.language()

    async def credits_start(self, object_id: UUID) -> float | None:
        """#101: where a title's end credits begin (the player asks its media server)."""
        return await self.player.credits_start(object_id)

    def threshold(self, kind: str) -> float | None:
        if kind in self.config.thresholds:
            value = self.config.thresholds[kind]
            return value if value > 0 else None
        media_type = self.types.get(kind)
        return media_type.finished_threshold if media_type is not None else 0.9

    async def refresh_config(self) -> None:
        reader = self._config_reader()
        if reader is None:
            return
        try:
            values = {name: (await reader.get(key)).value for name, key in SETTINGS.items()}
            thresholds: dict[str, float] = {}
            for media_type in self.types.all():
                try:
                    thresholds[media_type.kind] = float(
                        (await reader.get(threshold_key(media_type.kind))).value
                    )
                except Exception:  # noqa: S112 — kinds without a threshold setting keep the registry value
                    continue
            self.config = replace(self.config, **values, thresholds=thresholds)
        except Exception:
            log.warning("media configuration not refreshed")

    # --- registration ----------------------------------------------------------------------------------
    def register(self) -> None:
        self.ai_tools.register(self.assistant_tools)
        register_media_signals(default_signals)  # issue 122: the plays under way, for automations
        if not any(p.instance_ref == "media" for p in self.capabilities.system_providers(ATTENTION)):
            # #98: what waits for an administrator here — a badge on the navigation
            self.capabilities.provide(
                ATTENTION,
                RequestsAttention(self.database, self.authorizer),
                instance_ref="media",
                owner=OWNER,
            )
        if not any(p.instance_ref == "media.feed" for p in self.capabilities.system_providers(ATTENTION)):
            # #299: what arrived for a member since they last read « Mon fil »
            self.capabilities.provide(
                ATTENTION, FeedAttention(self.feed), instance_ref="media.feed", owner=OWNER
            )
        register_baseline(self.types, OWNER)
        if self.calendar.get(MediaReleaseCalendarSource.kind) is None:  # 027: releases in the calendar
            self.calendar.register(MediaReleaseCalendarSource(self.upcoming), owner=OWNER)
        if not self.capabilities.system_providers(MENTIONS):  # #299: the news linked to the library
            self.capabilities.provide(
                MENTIONS, LibraryMentions(self.database), instance_ref="media", owner=OWNER
            )
        if not self.capabilities.system_providers(DIGEST):  # 027: the newsletters' source
            self.capabilities.provide(
                DIGEST,
                LibraryDigest(self.database, self.upcoming, self.clock),
                instance_ref="media",
                owner=OWNER,
            )
        register_event_types(self.event_types)
        for capability, sink in ((LIBRARY, self.library), (REQUESTS, self.request_sink)):
            if self.sinks.get(capability) is None:
                self.sinks.register(capability, sink, owner=OWNER)
        # 027: history and metadata are pulled by the module, yet synced from the services page like the rest
        for capability, driver in ((ACTIVITY_HISTORY, self.ingestor), (METADATA, self.enricher)):
            if self.sinks.driver(capability) is None:
                self.sinks.register_driver(capability, driver, owner=OWNER)
        ports: tuple[tuple[str, Any], ...] = (
            (CATALOG, self.catalog_port),
            (HISTORY, self.history_reader),
            (QUOTA, self.quota),
            (RESCUES, self.cleanup),
            (RADIO_CREDITS, self.radio),
            (CARD_SOURCES, MediaCardSources(self.database, self.capabilities, self.enricher)),  # issue 229
            (GAME_SOURCES, MediaGameSources(self.database, self.capabilities, self.enricher)),  # issue 265
            (RECOMMENDATIONS, self.recommender),
            (ACTIVITY, MediaActivityAttributes(self.database)),
        )
        for name, provider in ports:
            if not any(p.instance_ref == "media" for p in self.capabilities.system_providers(name)):
                self.capabilities.provide(name, provider, instance_ref="media", owner=OWNER)
        participant = MediaParticipant(self.database)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == "media" for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref="media", owner=OWNER)
        default_retention_targets.register(
            RetentionTarget(
                "media.playback_sessions",
                "media.playback_sessions",
                "activity",
                "updated_at",
                "delete",
                OWNER,
                window=lambda: timedelta(days=90),
            )
        )
        for consumer in (
            self.history.consumer(),
            RequestWatched(self.database, self.events).consumer(),
            LeavingWatched(self.database, self.events, self.cleanup).consumer(),  # issue 228
            PortalActivity(self.database, clock=self.clock).consumer(),  # #282
        ):
            if self.consumers.get(consumer.name) is None:
                self.consumers.register(consumer)
        widgets: tuple[tuple[Any, Any], ...] = (
            (CONTINUE, ContinueWidget(self.history, self.clock, self.enricher, self.player)),
            (RECENT, RecentWidget(self.discovery, self.clock)),
            (REQUESTS_WIDGET, RequestsWidget(self.requests, self.clock)),
            (STATS_WIDGET, StatsWidget(self.database, self.insights, self.clock)),
            (RECENTLY_ADDED, RecentlyAddedWidget(self.database, self.clock)),
            (RECENT_RELEASES, RecentlyAddedWidget(self.database, self.clock, released=True)),
            (RECENTLY_REQUESTED, RecentlyRequestedWidget(self.database, self.clock, self.enricher)),
            (UPCOMING_WIDGET, UpcomingWidget(self.database, self.upcoming, self.clock, self.enricher)),
            (TOP_WIDGET, TopWidget(self.database, self.insights, self.clock)),
            (MY_SOON, MySoonWidget(self.database, self.request_insights, self.clock, self.enricher)),
            (
                DOWNLOADS_WIDGET,
                DownloadsWidget(self.database, self.request_insights, self.clock, self.enricher),
            ),
            (LEAVING_WIDGET, LeavingWidget(self.database, self.cleanup, self.clock)),
            (NEXT_RELEASES, NextReleasesWidget(self.database, self.upcoming, self.clock, self.enricher)),
            (POSTER_WALL, PosterWallWidget(self.database, self.insights, self.clock)),
            (SHUFFLE_WIDGET, ShuffleWidget(self.database, self.clock)),
            (RADIO_WIDGET, RadioWidget(self.radio, self.clock)),
            (LIVING_WALL, LivingWallWidget(self.database, self.clock)),
            (SERVER_PLAYING, ServerPlayingWidget(self.database, self.clock, self.enricher)),
            (ON_THIS_DAY, OnThisDayWidget(self.database, self.clock, self.enricher)),
            (FOR_YOU, ForYouWidget(self.database, self.taste, self.clock)),  # issue 190
            (TASTE, TasteWidget(self.database, self.taste, self.clock)),
        )
        for definition, widget in widgets:
            if self.widgets.get(definition.key) is None:
                self.widgets.register(definition, widget, owner=OWNER)
        if not any(p.kind == "media" for p in self.widgets.summaries()):  # 027: since your last visit
            self.widgets.register_summary(MediaChanges(self.database, self.authorizer), owner=OWNER)
        if self.search.provider("request") is None:  # #4: « Ask for it » in the search
            self.search.register(
                RequestableSearchProvider(self.requestable, self.authorizer, self.language), owner=OWNER
            )
        if self.search.provider("person") is None:  # #92: actors, directors, authors… a section of their own
            self.search.register(PeopleSearchProvider(self.people, self.authorizer), owner=OWNER)
        if self.search.provider("media") is None:
            self.search.register(MediaSearchProvider(self.catalog, self.authorizer), owner=OWNER)
            self.search.register_resolver(MediaResolver(self.catalog_port), owner=OWNER)
            for action in ACTIONS:
                self.search.register_action(action, owner=OWNER)
        for key, label, channels in CATEGORIES:
            if self.categories.get(key) is None:
                declare_category(key, OWNER, label, default_channels=channels, registry=self.categories)
        self.observables.declare(
            ObservedComponent(
                "media",
                OWNER,
                label="Media",
                functional_checks=(Check("catalog", self.probe),),
            )
        )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        jobs.register(
            IMAGE_JOB, self.images.run, idempotency="image ref checked before fetching", owner=OWNER
        )

        async def poll() -> None:
            await self.poller.tick()

        async def ingest() -> None:
            await self.ingestor.run()
            await self.history_rewards.run()
            await self.aggregator.run()

        async def aggregate() -> None:
            while await self.aggregator.run():
                pass

        async def enrich() -> None:
            await self.enricher.run()

        async def images() -> None:  # 027: covers whose fetch failed are tried again
            await self.images.backfill()

        # #256: books and audiobooks left without a word end, their minutes counted (#259: the radio too)
        async def sittings() -> None:
            while await self.books.sweep():
                pass
            while await self.radio.sweep():  # #259: the radio's too
                pass

        async def feed_notices() -> None:  # #299: what arrived in « Mon fil », told once
            providers = self.capabilities.system_providers(NOTIFY)
            if providers:
                await self.feed.notify_due(providers[0].provider)

        return [
            self.start,
            register_periodic(jobs, self.database, POLL_JOB, timedelta(seconds=15), poll, owner=OWNER),
            register_periodic(
                jobs, self.database, "media.feed_notices", timedelta(minutes=30), feed_notices, owner=OWNER
            ),
            register_periodic(
                jobs,
                self.database,
                ACTIVITY_JOB,
                timedelta(minutes=10),
                ingest,
                owner=OWNER,
                timeout_seconds=1800,
            ),
            register_periodic(
                jobs, self.database, AGGREGATE_JOB, timedelta(minutes=2), aggregate, owner=OWNER
            ),
            register_periodic(
                jobs, self.database, "media.images_backfill", timedelta(hours=1), images, owner=OWNER
            ),
            register_periodic(
                jobs, self.database, "media.books_sweep", timedelta(minutes=5), sittings, owner=OWNER
            ),
            register_periodic(
                jobs,
                self.database,
                ENRICH_JOB,
                timedelta(minutes=2),
                enrich,
                owner=OWNER,
                timeout_seconds=900,
            ),
        ]

    async def run_now(self, what: str) -> None:
        """Queue an immediate run of the history ingestion or of the metadata enrichment (027)."""
        kind = ACTIVITY_JOB if what == "history" else ENRICH_JOB
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            await enqueue(
                uow.session,
                kind=kind,
                dedup_key=f"{kind}:manual:{now.strftime('%Y%m%dT%H%M')}",
                run_at=now,
                clock=self.clock,
            )

    async def start(self) -> None:
        await self.refresh_config()

    # --- status ----------------------------------------------------------------------------------------
    async def status(self) -> dict[str, Any]:
        async with self.database.session() as session:
            unresolved = await session.scalar(select(func.count()).where(SourceItem.object_id.is_(None)))
            candidates = await session.scalar(select(func.count()).where(MatchCandidate.state == "proposed"))
            unlinked = await session.scalar(
                select(func.count()).where(
                    PlaybackSession.user_id.is_(None), PlaybackSession.ended.is_(False)
                )
            )
            per_service = {
                str(service): last
                for service, last in await session.execute(
                    select(SourceItem.service_id, func.max(SourceItem.last_seen_at)).group_by(
                        SourceItem.service_id
                    )
                )
            }
        metrics.gauge("media.match_candidates", float(candidates or 0))
        return {
            "unresolved_items": int(unresolved or 0),
            "match_candidates": int(candidates or 0),
            "unlinked_sessions": int(unlinked or 0),
            "freshness": {k: v.isoformat() if v else None for k, v in per_service.items()},
            "metrics": metrics.snapshot(),
        }

    async def probe(self) -> CheckResult:
        status = await self.status()
        facts = {k: status[k] for k in ("unresolved_items", "match_candidates", "unlinked_sessions")}
        failures = int(status["metrics"].get("media.playback.poll_failures", 0))
        if failures:
            return CheckResult("degraded", "some playback polls failed", {**facts, "poll_failures": failures})
        return CheckResult("ok", "the media catalog is fresh", facts)

    async def object_exists(self, object_id: UUID) -> bool:
        async with self.database.session() as session:
            from portalab.modules.media.models import MediaObject

            return await session.get(MediaObject, object_id) is not None
