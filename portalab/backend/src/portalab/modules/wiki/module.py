"""Wiki module facade (spec 011)."""

from dataclasses import replace
from typing import Any

from portalab.capabilities.ai import AIToolRegistry, default_ai_tools
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.content import HELP, KNOWLEDGE, LinkResolverRegistry, default_link_resolvers
from portalab.capabilities.events import EventTypeRegistry, default_event_types
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
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.logging import get_logger
from portalab.core.time import Clock
from portalab.modules.wiki import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.wiki import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.wiki.ai_tools import WikiAiTools
from portalab.modules.wiki.events import register_event_types
from portalab.modules.wiki.knowledge import WikiKnowledge, WikiLinkResolver, WikiSearchProvider
from portalab.modules.wiki.pages import PageService
from portalab.modules.wiki.participant import WikiParticipant
from portalab.modules.wiki.settings import SETTINGS, WikiConfig

OWNER = "module:wiki"
log = get_logger("portalab.wiki")


class WikiModule:
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
        search: SearchRegistry = default_search,
        observables: ObservableRegistry = default_observables,
        ai_tools: AIToolRegistry = default_ai_tools,
    ) -> None:
        self.ai_tools = ai_tools  # issue 171: the assistant's tools
        self.database = database
        self.audit = audit
        self.capabilities = capabilities
        self.clock = clock
        self.config = WikiConfig()
        self.event_types = event_types
        self.resolvers = resolvers
        self.search = search
        self.observables = observables
        self.pages = PageService(database, events, authorizer, capabilities, lambda: self.config, clock=clock)
        self.knowledge = WikiKnowledge(self.pages)

    def register(self) -> None:
        WikiAiTools(self.pages, self.clock).register(self.ai_tools)  # issue 171
        register_event_types(self.event_types)
        ports: tuple[tuple[str, Any], ...] = ((KNOWLEDGE, self.knowledge), (HELP, self.knowledge))
        for name, provider in ports:
            if not self.capabilities.system_providers(name):
                self.capabilities.provide(name, provider, instance_ref="wiki", owner=OWNER)
        participant = WikiParticipant(self.database)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == "wiki" for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref="wiki", owner=OWNER)
        if self.resolvers.get("wiki") is None:
            self.resolvers.register(WikiLinkResolver(self.pages), owner=OWNER)
        if self.search.provider("wiki") is None:
            self.search.register(WikiSearchProvider(self.pages), owner=OWNER)
        self.observables.declare(
            ObservedComponent("wiki", OWNER, label="Wiki", functional_checks=(Check("links", self.probe),))
        )

    async def probe(self) -> CheckResult:
        """Broken internal links between wiki pages (report size)."""
        from portalab.core.authz_port import Principal

        broken = await self.pages.broken_links(Principal(channel="system"))
        if broken:
            return CheckResult(
                "degraded", f"{len(broken)} broken wiki link(s)", {"broken_links": len(broken)}
            )
        return CheckResult("ok", "no broken wiki links", {"broken_links": 0})

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("wiki configuration not refreshed")
