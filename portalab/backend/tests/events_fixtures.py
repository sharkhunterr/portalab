"""Spec 007 fixtures: an Events module on the store-backed publisher, with isolated registries."""

from dataclasses import dataclass, field
from pathlib import Path

from portalab.capabilities.events import ConsumerRegistry, EventType, EventTypeRegistry
from portalab.core.db import Database
from portalab.core.time import Clock
from portalab.modules.events.module import EventsModule
from portalab.modules.events.publisher.publisher import EventStorePublisher
from portalab.modules.events.settings import EventsConfig
from tests.privacy_fixtures import FullPlatform, make_full_platform

OWNER = "test:events"


@dataclass
class EventsHarness:
    full: FullPlatform
    module: EventsModule
    types: EventTypeRegistry
    consumers: ConsumerRegistry = field(default_factory=ConsumerRegistry)

    @property
    def publisher(self) -> EventStorePublisher:
        return self.module.publisher


def make_events(database: Database, blob_root: Path, clock: Clock | None = None) -> EventsHarness:
    full = make_full_platform(database, blob_root, clock)
    types = EventTypeRegistry()
    for name in (
        "events.quarantined",
        "events.consumer_dead_lettered",
        "events.replay_started",
        "events.replay_finished",
    ):
        types.register(
            EventType(
                name=name, owner="module:events", retention_class="technical", visibility_class="restricted"
            )
        )
    consumers = ConsumerRegistry()
    module = EventsModule(
        database,
        full.authz.audit,
        full.identity.capabilities,
        event_types=types,
        consumers=consumers,
        visibility=full.privacy.filter,
        config=EventsConfig(max_delivery_attempts=3, retry_backoff_seconds=0),
        clock=clock,
    )
    return EventsHarness(full, module, types, consumers)
