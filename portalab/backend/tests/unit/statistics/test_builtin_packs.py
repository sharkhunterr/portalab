"""017 T023 (#84) — the shipped definition packs hold: every definition validates against the event types
their owners really register (an invalid one would only be skipped with a warning at start-up), and every
title and description is translated in English and French."""

import json

import pytest

from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.service_events import register_status_changed
from portalab.capabilities.statistics import PackRegistry, StatisticDefinition
from portalab.core.event_port import OutboxEventPublisher
from portalab.modules.community.events.types import register_event_types as register_community
from portalab.modules.community.proposals.types import register_slice_d_types
from portalab.modules.gamification.events import register_event_types as register_gamification
from portalab.modules.i18n.catalog.service import LOCALES_DIR
from portalab.modules.identity import event_types as _identity_types  # noqa: F401 — user.* types
from portalab.modules.marketplace.events import register_event_types as register_marketplace
from portalab.modules.media.events import register_event_types as register_media
from portalab.modules.statistics.definitions.service import DefinitionService
from portalab.modules.statistics.packs.registry import register_builtin
from portalab.modules.statistics.settings import StatisticsConfig
from portalab.modules.support.events import register_event_types as register_support


def production_types() -> EventTypeRegistry:
    types = EventTypeRegistry()
    for event_type in default_event_types.all():
        if event_type.owner == "module:identity":
            types.register(event_type)
    register_status_changed(types)
    for register in (
        register_media,
        register_community,
        register_slice_d_types,
        register_gamification,
        register_marketplace,
        register_support,
    ):
        register(types)
    return types


def builtin() -> list[StatisticDefinition]:
    packs = PackRegistry()
    register_builtin(packs)
    return [definition for definition, _, _ in packs.definitions()]


DEFINITIONS = builtin()


@pytest.mark.parametrize("definition", DEFINITIONS, ids=lambda d: d.key)
def test_builtin_definition_is_valid(definition: StatisticDefinition) -> None:
    service = DefinitionService(None, OutboxEventPublisher(), None, production_types(), StatisticsConfig)  # type: ignore[arg-type]
    service.validate(definition)  # raises InvalidDefinition with the reasons
    assert definition.key.split(".")[0] == definition.domain


@pytest.mark.parametrize("language", ["en", "fr"])
def test_builtin_definitions_are_translated(language: str) -> None:
    missing = []
    for definition in DEFINITIONS:
        for key in (definition.title_key, definition.description_key):
            namespace, _, message = (key or "").partition(":")
            path = LOCALES_DIR / language / f"{namespace}.json"
            catalog = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            if key and message not in catalog:
                missing.append(key)
    assert missing == []
