"""i18n module facade (spec 026)."""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.i18n import CONTENT, FORMATTER, RENDERER, RESOLVER, TIME
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.plugins import I18N_CATALOGS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.core.audit_port import AuditSink
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock
from portalab.modules.i18n import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.i18n import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.i18n.adapters.locale_for_user import RecipientLocale, ResponseLanguage
from portalab.modules.i18n.adapters.presentation import Presentation
from portalab.modules.i18n.admin import CatalogAdmin
from portalab.modules.i18n.catalog.plugins import PluginCatalogs, default_plugin_catalogs
from portalab.modules.i18n.catalog.service import CatalogService
from portalab.modules.i18n.content.localizer import ContentKinds, ContentLocalizer, default_content_kinds
from portalab.modules.i18n.events import (
    CONSUMER,
    plugin_state_consumer,
    policy_consumer,
    register_event_types,
)
from portalab.modules.i18n.format.formatter import Formatter
from portalab.modules.i18n.models import MissingKeyStat
from portalab.modules.i18n.resolver.resolver import LocaleResolver
from portalab.modules.i18n.time.renderer import TimeRenderer
from portalab.modules.i18n.validators import I18nValidators

OWNER = "module:i18n"
FALLBACK_RATE_DEGRADED = 0.2


class I18nModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        plugins: PluginCatalogs = default_plugin_catalogs,
        content_kinds: ContentKinds = default_content_kinds,
        event_types: EventTypeRegistry = default_event_types,
        consumers: ConsumerRegistry = default_consumers,
        observables: ObservableRegistry = default_observables,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.resolver = LocaleResolver(capabilities)
        self.catalogs = CatalogService(database, plugins=plugins, clock=clock)
        self.plugins = plugins
        self.formatter = Formatter()
        self.time = TimeRenderer(self.formatter)
        self.content = ContentLocalizer(database, clock=clock)
        self.content_kinds = content_kinds
        self.admin = CatalogAdmin(database, self.catalogs, audit, events, clock=clock)
        self.validators = I18nValidators(database, self.resolver.policy)
        self.recipients = RecipientLocale(self.resolver)
        self.response_language = ResponseLanguage(self.resolver)
        self.presentation = Presentation(self.formatter, self.catalogs)
        self.event_types = event_types
        self.consumers = consumers
        self.observables = observables

    def register(self) -> None:
        for name, provider in (
            (RESOLVER, self.resolver),
            (RENDERER, self.catalogs),
            (FORMATTER, self.formatter),
            (TIME, self.time),
            (CONTENT, self.content),
            (I18N_CATALOGS, self.plugins),
        ):
            if not self.capabilities.system_providers(name):
                self.capabilities.provide(name, provider, instance_ref="i18n", owner=OWNER)
        register_event_types(self.event_types)
        if self.consumers.get(CONSUMER) is None:

            async def enabled() -> Any:
                return (await self.resolver.policy()).enabled_languages

            self.consumers.register(
                policy_consumer(self.database, lambda: self.events, self.resolver.bump, enabled)
            )
        if self.consumers.get("i18n.plugin_catalogs") is None:
            self.consumers.register(plugin_state_consumer(self.plugins))
        default_retention_targets.register(
            RetentionTarget(
                "i18n.missing_key_stats",
                "i18n.missing_key_stats",
                "technical",
                "last_seen_at",
                "delete",
                OWNER,
                window=lambda: timedelta(days=90),
            )
        )

        async def fallback_rate() -> CheckResult:
            await self.catalogs.flush_missing()
            async with self.database.session() as session:
                misses = int(
                    await session.scalar(select(func.coalesce(func.sum(MissingKeyStat.count), 0))) or 0
                )
            facts = {"missing_lookups": misses}
            return CheckResult(
                "degraded" if misses > 1000 else "ok",
                "missing translations" if misses > 1000 else "catalogs complete",
                facts,
            )

        self.observables.declare(
            ObservedComponent(
                "i18n", OWNER, label="Languages", functional_checks=(Check("fallbacks", fallback_rate),)
            )
        )

    async def health(self) -> dict[str, Any]:
        await self.catalogs.flush_missing()
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(MissingKeyStat).order_by(MissingKeyStat.count.desc()).limit(50)
                    )
                )
                .scalars()
                .all()
            )
        by_language: dict[str, int] = {}
        for row in rows:
            by_language[row.language] = by_language.get(row.language, 0) + row.count
        return {
            "missing": [
                {
                    "namespace": r.namespace,
                    "language": r.language,
                    "key": r.key,
                    "count": r.count,
                    "last_seen_at": r.last_seen_at.isoformat(),
                }
                for r in rows
            ],
            "missing_by_language": by_language,
            "plugins": {plugin: list(languages) for plugin, languages in self.plugins.languages().items()},
        }
