"""Spec 022 fixtures: the UI module on the full platform (administration config + preferences)."""

from dataclasses import dataclass
from pathlib import Path

from portalab.capabilities.events import ConsumerRegistry, EventTypeRegistry
from portalab.core.db import Database
from portalab.core.time import Clock
from portalab.modules.ui.module import UiModule
from tests.privacy_fixtures import FullPlatform, make_full_platform


@dataclass
class UiHarness:
    full: FullPlatform
    module: UiModule
    event_types: EventTypeRegistry
    consumers: ConsumerRegistry


async def make_ui(database: Database, blob_root: Path, clock: Clock | None = None) -> UiHarness:
    full = make_full_platform(database, blob_root, clock)
    await full.authz.catalog.sync()
    event_types, consumers = EventTypeRegistry(), ConsumerRegistry()
    module = UiModule(
        database,
        full.authz.engine.events,
        full.authz.audit,
        full.identity.capabilities,
        clock=clock,
        event_types=event_types,
        consumers=consumers,
    )
    module.register()
    full.administration.registry.register_validator(
        "ui.theme", module.themes.choice_errors, owner="module:ui"
    )
    return UiHarness(full, module, event_types, consumers)
