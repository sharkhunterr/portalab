"""UI module facade (spec 022): theme registry, appearance policy and UI preference events."""

from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.plugins import THEME_REGISTRY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import CAPABILITY as THEME_CATALOG
from portalab.core.audit_port import AuditSink
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock
from portalab.modules.ui import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.ui import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.ui.events import CONSUMER, preference_consumer, register_event_types
from portalab.modules.ui.themes.service import ThemeService

OWNER = "module:ui"


class UiModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
        event_types: EventTypeRegistry = default_event_types,
        consumers: ConsumerRegistry = default_consumers,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.themes = ThemeService(database, audit, capabilities, clock=clock)
        self.event_types = event_types
        self.consumers = consumers

    def register(self) -> None:
        if not self.capabilities.system_providers(THEME_CATALOG):
            self.capabilities.provide(THEME_CATALOG, self.themes, instance_ref="ui", owner="module:ui")
        if not self.capabilities.system_providers(THEME_REGISTRY):
            self.capabilities.provide(THEME_REGISTRY, self.themes, instance_ref="ui", owner="module:ui")
        if self.event_types.get("theme.changed") is None:
            register_event_types(self.event_types)
        if self.consumers.get(CONSUMER) is None:
            self.consumers.register(preference_consumer(self.database, lambda: self.events))
