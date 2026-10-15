"""UI module facade (spec 022): theme registry, appearance policy and UI preference events."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.plugins import THEME_REGISTRY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import CAPABILITY as THEME_CATALOG
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock
from portalab.modules.ui import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.ui import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.ui.events import CONSUMER, preference_consumer, register_event_types
from portalab.modules.ui.looks import NotificationLooks
from portalab.modules.ui.themes.service import ThemeService
from portalab.modules.ui.visuals.service import VisualPacks
from portalab.modules.ui.weather import WeatherService

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
        visuals_root: Path | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.themes = ThemeService(database, audit, capabilities, clock=clock)
        self.weather = WeatherService(capabilities)  # #68: the « live weather » ambience
        self.looks = NotificationLooks(capabilities)
        # issue 1 (POC): imported visual packs, kept under ``DATA_DIR/visuals``
        self.visuals = (
            VisualPacks(
                visuals_root, capabilities, themes=self.themes, audit=self._audit_visuals(database, audit)
            )
            if visuals_root
            else None
        )
        self.event_types = event_types
        self.consumers = consumers

    @staticmethod
    def _audit_visuals(
        database: Database, audit: AuditSink
    ) -> Callable[[Principal | None, str, dict[str, Any]], Awaitable[None]]:
        """issue 1: every action on a visual pack in the audit log, sensitive (it runs in members' pages)."""

        async def record(actor: Principal | None, action: str, context: dict[str, Any]) -> None:
            async with database.unit_of_work() as uow:
                await audit.record(
                    uow.session,
                    AuditRecord(
                        action=action,
                        actor=actor or Principal(channel="system"),
                        resource=ResourceRef("visual_pack", str(context.get("pack") or "inbox")),
                        decision="allow",
                        result="success",
                        context=context,
                        sensitive=True,
                    ),
                )

        return record

    def register(self) -> None:
        if not self.capabilities.system_providers(THEME_CATALOG):
            self.capabilities.provide(THEME_CATALOG, self.themes, instance_ref="ui", owner="module:ui")
        if not self.capabilities.system_providers(THEME_REGISTRY):
            self.capabilities.provide(THEME_REGISTRY, self.themes, instance_ref="ui", owner="module:ui")
        if self.event_types.get("theme.changed") is None:
            register_event_types(self.event_types)
        if self.consumers.get(CONSUMER) is None:
            self.consumers.register(preference_consumer(self.database, lambda: self.events))
