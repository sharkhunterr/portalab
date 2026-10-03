"""Module wiring at the composition root: build each module from the kernel services.

Order matters: authorization (spec 003) first — it provides the Authorizer engine, the database ``AuditSink``
and the ``authz.admin_authority`` capability — then identity (spec 002), which consumes them. The event
publisher is the kernel outbox until the Events module (spec 007) replaces it.
"""

import hashlib
import hmac
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink, LogAuditSink
from portalab.core.authz_port import Authorizer, DenyAllAuthorizer, Principal, ResourceRef
from portalab.core.blobstore import FileSystemBlobStore
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, OutboxEventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.secrets import SecretBox
from portalab.modules.administration.module import AdministrationModule
from portalab.modules.ai.module import AiModule
from portalab.modules.authz.module import AuthzModule
from portalab.modules.automations.module import AutomationsModule
from portalab.modules.calendar.module import CalendarModule
from portalab.modules.campaigns.module import CampaignsModule
from portalab.modules.community.module import CommunityModule
from portalab.modules.connectors.module import ConnectorsModule
from portalab.modules.content.module import ContentModule
from portalab.modules.dashboard.module import DashboardModule
from portalab.modules.events.module import EventsModule
from portalab.modules.events.publisher.publisher import EventStorePublisher
from portalab.modules.gamification.module import GamificationModule
from portalab.modules.health.module import HealthModule
from portalab.modules.i18n.module import I18nModule
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.module import IdentityModule
from portalab.modules.marketplace.module import MarketplaceModule
from portalab.modules.media.module import MediaModule
from portalab.modules.news.module import NewsModule
from portalab.modules.notifications.module import NotificationsModule
from portalab.modules.observability.module import ObservabilityModule
from portalab.modules.plugins.module import PluginsModule
from portalab.modules.privacy.module import PrivacyModule
from portalab.modules.search.module import SearchModule
from portalab.modules.shell.module import ShellModule
from portalab.modules.statistics.module import StatisticsModule
from portalab.modules.support.module import SupportModule
from portalab.modules.ui.module import UiModule
from portalab.modules.wiki.module import WikiModule


class DeferredAuthorizer:
    """Delegates to an authorizer installed later (the database is only known at application start-up)."""

    def __init__(self) -> None:
        self.target: Authorizer = DenyAllAuthorizer()

    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        return await self.target.is_allowed(principal, permission, resource)


def wire_authz(database: Database, events: EventPublisher, capabilities: CapabilityRegistry) -> AuthzModule:
    module = AuthzModule(database, events, capabilities)
    module.register_capabilities()
    return module


def default_identity_context(
    database: Database,
    *,
    data_dir: Path,
    capabilities: CapabilityRegistry,
    authorizer: Authorizer,
    audit: AuditSink | None = None,
    events: EventPublisher | None = None,
) -> IdentityContext:
    return IdentityContext(
        database=database,
        events=events or OutboxEventPublisher(),
        audit=audit or LogAuditSink(),
        capabilities=capabilities,
        blobs=FileSystemBlobStore(data_dir / "blobs"),
        authorizer=authorizer,
    )


def wire_identity(context: IdentityContext, *, jobs: JobRegistry | None = None) -> IdentityModule:
    module = IdentityModule(context)
    module.register_capabilities()
    if jobs is not None:
        module.register_jobs(jobs)
    return module


@dataclass
class Platform:
    authz: AuthzModule
    privacy: PrivacyModule
    administration: AdministrationModule
    identity: IdentityModule
    events: EventsModule
    connectors: ConnectorsModule
    health: HealthModule
    observability: ObservabilityModule
    ui: UiModule
    shell: ShellModule
    i18n: I18nModule
    search: SearchModule
    dashboard: DashboardModule
    support: SupportModule
    statistics: StatisticsModule
    notifications: NotificationsModule
    media: MediaModule
    content: ContentModule
    wiki: WikiModule
    news: NewsModule
    calendar: CalendarModule
    ai: AiModule
    gamification: GamificationModule
    campaigns: CampaignsModule
    automations: AutomationsModule
    community: CommunityModule
    marketplace: MarketplaceModule
    plugins: PluginsModule
    seeds: list[Callable[[], Awaitable[None]]]

    async def seed_periodic_jobs(self) -> None:
        for seed in self.seeds:
            await seed()

    async def refresh_config(self) -> bool:
        from portalab.app.config_bindings import safe_refresh

        return await safe_refresh(self)

    async def start_services(self) -> bool:
        """Provide the capabilities of the enabled services in this process (spec 005)."""
        try:
            await self.connectors.start()
        except Exception:
            return False
        return True


def wire_platform(
    database: Database,
    *,
    data_dir: Path,
    capabilities: CapabilityRegistry,
    secret_key: bytes,
    jobs: JobRegistry | None = None,
) -> Platform:
    """Production wiring shared by ``serve``, ``worker`` and the CLI."""
    events = EventStorePublisher()
    authz = wire_authz(database, events, capabilities)
    privacy = PrivacyModule(database, events, authz.audit, capabilities)
    privacy.register_capabilities()
    administration = AdministrationModule(
        database, events, authz.audit, capabilities, authz.engine, SecretBox(secret_key)
    )
    administration.register_capabilities()
    context = default_identity_context(
        database,
        data_dir=data_dir,
        capabilities=capabilities,
        authorizer=authz.engine,
        audit=authz.audit,
        events=events,
    )
    context.visibility = privacy.filter
    identity = wire_identity(context, jobs=jobs)
    events_module = EventsModule(
        database, authz.audit, capabilities, visibility=privacy.filter, publisher=events
    )
    events_module.register()
    connectors = ConnectorsModule(
        database, events, authz.audit, capabilities, SecretBox(secret_key), authorizer=authz.engine
    )
    connectors.register_capabilities()
    health = HealthModule(database, events, authz.audit, capabilities)
    health.register_capabilities()
    observability = ObservabilityModule(database, events, authz.audit, capabilities)
    observability.register_capabilities()
    ui = UiModule(database, events, authz.audit, capabilities)
    ui.register()
    administration.registry.register_validator("ui.theme", ui.themes.choice_errors, owner="module:ui")
    shell = ShellModule(database, events, authz.engine, capabilities)
    shell.register()
    i18n = I18nModule(database, events, authz.audit, capabilities)
    i18n.register()
    for key, validator in i18n.validators.table().items():
        administration.registry.register_validator(key, validator, owner="module:i18n")
    notifications = NotificationsModule(database, events, authz.audit, capabilities, authz.engine)
    notifications.register()
    support = SupportModule(database, events, authz.audit, capabilities, authz.engine, blobs=context.blobs)
    support.register()
    statistics = StatisticsModule(
        database,
        events,
        authz.audit,
        capabilities,
        authz.engine,
        salt=hmac.new(secret_key, b"portalab.statistics.members", hashlib.sha256).digest(),
        visibility=privacy.filter,
    )
    statistics.register()
    media = MediaModule(
        database,
        events,
        authz.audit,
        capabilities,
        authz.engine,
        blobs=context.blobs,
        visibility=privacy.filter,
    )
    media.register()
    content = ContentModule(database, capabilities, authz.engine, blobs=context.blobs)
    content.register()
    wiki = WikiModule(database, events, authz.audit, capabilities, authz.engine)
    wiki.register()
    news = NewsModule(database, events, authz.audit, capabilities, authz.engine)
    news.register()
    calendar = CalendarModule(database, events, capabilities, authz.engine)
    calendar.register()
    search = SearchModule(database, events, authz.audit, capabilities, authz.engine)
    search.register()
    dashboard = DashboardModule(database, events, authz.audit, capabilities, authz.engine)
    dashboard.register()
    for key, validator in dashboard.validators.table().items():
        administration.registry.register_validator(key, validator, owner="module:dashboard")
    ai = AiModule(database, events, authz.audit, capabilities, authz.engine)
    ai.register()
    gamification = GamificationModule(
        database, events, authz.audit, capabilities, authz.engine, visibility=privacy.filter
    )
    gamification.register()
    campaigns = CampaignsModule(database, events, authz.audit, capabilities, authz.engine)
    campaigns.register()
    automations = AutomationsModule(database, events, authz.audit, capabilities, authz.engine)
    automations.register()
    community = CommunityModule(
        database, events, authz.audit, capabilities, authz.engine, visibility=privacy.filter
    )
    community.register()
    marketplace = MarketplaceModule(database, events, authz.audit, capabilities, authz.engine)
    marketplace.register()
    plugins = PluginsModule(
        database, events, authz.audit, capabilities, authz.engine, root=data_dir / "plugins"
    )
    plugins.register()
    seeds: list[Callable[[], Awaitable[None]]] = []
    if jobs is not None:
        seeds.extend(privacy.register_jobs(jobs))
        seeds.append(
            register_periodic(
                jobs,
                database,
                "audit.partition_maintenance",
                timedelta(days=1),
                lambda: authz.maintain_audit_partitions(privacy.config.audit_retention_months),
                owner="module:authz",
            )
        )
        seeds.append(
            register_periodic(
                jobs,
                database,
                "audit.checkpoint",
                timedelta(hours=1),
                authz.seal_audit_checkpoint,
                owner="module:authz",
            )
        )
        seeds.append(identity.ensure_sweeps_scheduled)
        seeds.append(connectors.register_jobs(jobs))
        seeds.extend(health.register_jobs(jobs))
        seeds.extend(observability.register_jobs(jobs))
        seeds.extend(search.register_jobs(jobs))
        seeds.extend(statistics.register_jobs(jobs))
        seeds.extend(notifications.register_jobs(jobs))
        seeds.extend(media.register_jobs(jobs))
        seeds.extend(support.register_jobs(jobs))
        seeds.extend(news.register_jobs(jobs))
        seeds.extend(calendar.register_jobs(jobs))
        seeds.extend(ai.register_jobs(jobs))
        seeds.extend(gamification.register_jobs(jobs))
        seeds.extend(campaigns.register_jobs(jobs))
        seeds.extend(automations.register_jobs(jobs))
        seeds.extend(community.register_jobs(jobs))
        seeds.extend(marketplace.register_jobs(jobs))
        seeds.extend(plugins.register_jobs(jobs))
    platform = Platform(
        authz,
        privacy,
        administration,
        identity,
        events_module,
        connectors,
        health,
        observability,
        ui,
        shell,
        i18n,
        search,
        dashboard,
        support,
        statistics,
        notifications,
        media,
        content,
        wiki,
        news,
        calendar,
        ai,
        gamification,
        campaigns,
        automations,
        community,
        marketplace,
        plugins,
        seeds,
    )
    from portalab.app.config_bindings import bind

    bind(platform)
    return platform
