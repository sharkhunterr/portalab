"""Events module facade (spec 007): store-backed publisher, dispatcher, quarantine, history, replay."""

from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink
from portalab.core.db import Database
from portalab.core.time import Clock
from portalab.core.visibility_port import VisibilityFilter
from portalab.modules.events import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.events import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.events import types as _types  # noqa: F401 — registers own event types
from portalab.modules.events.consumers.live import NAME as LIVE
from portalab.modules.events.consumers.live import live_consumer
from portalab.modules.events.consumers.runtime import Dispatcher
from portalab.modules.events.history.query import HistoryQuery
from portalab.modules.events.publisher.publisher import EventStorePublisher
from portalab.modules.events.quarantine.service import QuarantineService
from portalab.modules.events.replay.service import ReplayService
from portalab.modules.events.retention import register_targets
from portalab.modules.events.settings import EventsConfig

OWNER = "module:events"


class EventsModule:
    def __init__(
        self,
        database: Database,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        *,
        event_types: EventTypeRegistry = default_event_types,
        consumers: ConsumerRegistry = default_consumers,
        visibility: VisibilityFilter | None = None,
        config: EventsConfig | None = None,
        clock: Clock | None = None,
        publisher: EventStorePublisher | None = None,
    ) -> None:
        self.config = config or EventsConfig()
        self.database = database
        self.capabilities = capabilities
        self.event_types = event_types
        self.consumers = consumers
        self.publisher = publisher or EventStorePublisher(event_types, clock=clock)
        self.dispatcher = Dispatcher(
            database, consumers, event_types, self.publisher, config=self.config, clock=clock
        )
        self.quarantine = QuarantineService(database, audit, clock=clock)
        self.history = HistoryQuery(database, visibility, event_types=event_types)
        self.replay = ReplayService(database, self.publisher, audit, consumers=consumers, clock=clock)

    def register(self) -> None:
        if self.consumers.get(LIVE) is None:
            self.consumers.register(live_consumer(self.database, self.event_types))
        register_targets(lambda: self.config)
