"""News module facade (spec 011)."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from portalab.capabilities.ai import AIToolRegistry, default_ai_tools
from portalab.capabilities.automation_actions import ActionRegistry, default_actions
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.content import (
    SOURCE_ITEMS,
    CalendarSourceRegistry,
    LinkResolverRegistry,
    default_calendar_sources,
    default_link_resolvers,
)
from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.navigation.attention import ATTENTION
from portalab.capabilities.notifications import CategoryRegistry, declare_category, default_categories
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import SearchRegistry, default_search
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.logging import get_logger
from portalab.core.time import Clock
from portalab.modules.news import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.news import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.news.ai_tools import NewsAiTools
from portalab.modules.news.articles import PUBLISH_JOB, ArticleService
from portalab.modules.news.attention import NewsAttention
from portalab.modules.news.editions.service import Editions
from portalab.modules.news.events import register_event_types
from portalab.modules.news.integrations import (
    FEATURED,
    LATEST,
    MY_FEED,
    MyFeedWidget,
    NewsCalendarSource,
    NewsLinkResolver,
    NewsSearchProvider,
    NewsWidget,
    register_publish_action,
)
from portalab.modules.news.newsletters import CATEGORY as NEWSLETTER_CATEGORY
from portalab.modules.news.newsletters import Newsletters
from portalab.modules.news.participant import NewsParticipant
from portalab.modules.news.settings import SETTINGS, NewsConfig
from portalab.modules.news.sources.service import FeedSources
from portalab.modules.news.summary import NewsChanges

OWNER = "module:news"
SWEEP_JOB = "news.publish_sweep"
NEWSLETTER_JOB = "news.newsletters"
SOURCES_JOB = "news.sources"  # #299
log = get_logger("portalab.news")


class NewsModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        event_types: EventTypeRegistry = default_event_types,
        resolvers: LinkResolverRegistry = default_link_resolvers,
        calendar: CalendarSourceRegistry = default_calendar_sources,
        search: SearchRegistry = default_search,
        widgets: WidgetRegistry = default_widgets,
        categories: CategoryRegistry = default_categories,
        actions: ActionRegistry = default_actions,
        observables: ObservableRegistry = default_observables,
        ai_tools: AIToolRegistry = default_ai_tools,
        blobs: BlobStore | None = None,
    ) -> None:
        self.ai_tools = ai_tools  # issue 171: the assistant's tools
        self.database = database
        self.audit = audit
        self.capabilities = capabilities
        self.clock = clock
        self.config = NewsConfig()
        self.event_types = event_types
        self.resolvers = resolvers
        self.calendar = calendar
        self.search = search
        self.widgets = widgets
        self.categories = categories
        self.actions = actions
        self.observables = observables
        self.articles = ArticleService(
            database, events, authorizer, capabilities, lambda: self.config, clock=clock
        )
        self.newsletters = Newsletters(database, self.articles, capabilities, clock=clock)  # 027
        self.articles.newsletter = self.newsletters.email_article
        self.editions = Editions(database, self.newsletters, clock=clock)  # #316: self-writing editions
        self.newsletters.editions = self.editions
        self.sources = FeedSources(database, capabilities, blobs, clock=clock)  # #299: news from elsewhere

    def register(self) -> None:
        NewsAiTools(self.articles, self.clock).register(self.ai_tools)  # issue 171
        register_event_types(self.event_types)
        participant = NewsParticipant(self.database)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == "news" for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref="news", owner=OWNER)
        if not any(p.instance_ref == "news" for p in self.capabilities.system_providers(SOURCE_ITEMS)):
            # #299: what the sources published, for « Mon fil »'s unread badge
            self.capabilities.provide(SOURCE_ITEMS, self.sources, instance_ref="news", owner=OWNER)
        if not any(p.instance_ref == "news" for p in self.capabilities.system_providers(ATTENTION)):
            # #336: the articles a member has not opened yet, on « Headlines »
            self.capabilities.provide(
                ATTENTION, NewsAttention(self.articles), instance_ref="news", owner=OWNER
            )
        if self.resolvers.get("news") is None:
            self.resolvers.register(NewsLinkResolver(self.articles), owner=OWNER)
        if self.calendar.get("news") is None:
            self.calendar.register(NewsCalendarSource(self.articles), owner=OWNER)
        if self.search.provider("news") is None:
            self.search.register(NewsSearchProvider(self.articles), owner=OWNER)
        for definition, featured in ((FEATURED, True), (LATEST, False)):
            if self.widgets.get(definition.key) is None:
                self.widgets.register(
                    definition, NewsWidget(self.articles, featured, self.clock), owner=OWNER
                )
        if self.widgets.get(MY_FEED.key) is None:
            self.widgets.register(MY_FEED, MyFeedWidget(self.sources, self.clock), owner=OWNER)
        if not any(p.kind == "news" for p in self.widgets.summaries()):  # 027: since your last visit
            self.widgets.register_summary(NewsChanges(self.articles), owner=OWNER)
        if self.categories.get("news.published") is None:
            declare_category("news.published", OWNER, "news:category.published", registry=self.categories)
        if self.categories.get(NEWSLETTER_CATEGORY) is None:  # 027: newsletters, by e-mail only
            declare_category(
                NEWSLETTER_CATEGORY,
                OWNER,
                "news:category.newsletter",
                default_channels=("email",),
                registry=self.categories,
            )
        register_publish_action(self.articles, self.actions)
        self.observables.declare(
            ObservedComponent(
                "news", OWNER, label="News", functional_checks=(Check("scheduled_publish", self.probe),)
            )
        )

    async def probe(self) -> CheckResult:
        """Scheduled articles whose time passed more than two minutes ago (the publish job is lagging)."""
        from sqlalchemy import func, select

        from portalab.core.time import utc_now
        from portalab.modules.news.models import Article

        async with self.database.session() as session:
            late = await session.scalar(
                select(func.count()).where(
                    Article.status == "scheduled",
                    Article.publish_at < utc_now(self.clock) - timedelta(minutes=2),
                )
            )
        if late:
            return CheckResult(
                "degraded", f"{late} scheduled article(s) not published yet", {"late": int(late)}
            )
        return CheckResult("ok", "scheduled publications are on time", {"late": 0})

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def publish(payload: dict[str, Any]) -> None:
            await self.articles.run_scheduled(payload)

        jobs.register(PUBLISH_JOB, publish, idempotency="state check + publish_seq", owner=OWNER)

        async def sweep() -> None:
            await self.articles.sweep()

        async def newsletters() -> None:
            await self.newsletters.run_due()

        async def sources() -> None:  # #299: each source read on its own cadence
            await self.sources.run_due()

        return [
            self.refresh_config,
            register_periodic(jobs, self.database, SWEEP_JOB, timedelta(minutes=1), sweep, owner=OWNER),
            register_periodic(
                jobs, self.database, NEWSLETTER_JOB, timedelta(minutes=10), newsletters, owner=OWNER
            ),
            register_periodic(
                jobs,
                self.database,
                SOURCES_JOB,
                timedelta(minutes=5),
                sources,
                owner=OWNER,
                timeout_seconds=280,
            ),
        ]

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("news configuration not refreshed")
