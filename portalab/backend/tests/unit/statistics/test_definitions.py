"""017 T004/T009/T026/T033 — closed definition schema (unknown or non-aggregatable fields, free expressions
and thresholds below the floor rejected); period boundaries in the statistics zone with the configured week
start; trends; owner-tagged pack registry (plugin packs namespaced and inactive)."""

from datetime import date

import pytest
from pydantic import ValidationError

from portalab.capabilities.events import EventType, EventTypeRegistry
from portalab.capabilities.statistics import DefinitionError, PackRegistry, Period, StatisticDefinition
from portalab.core.event_port import OutboxEventPublisher
from portalab.modules.statistics.definitions.service import DefinitionService, InvalidDefinition
from portalab.modules.statistics.period.resolver import PeriodInvalid, previous, resolve
from portalab.modules.statistics.privacy.guard import Cell, PrivacyGuard
from portalab.modules.statistics.settings import StatisticsConfig
from portalab.modules.statistics.trend.calculator import trend

BASE = {
    "key": "media.minutes",
    "title_key": "t",
    "domain": "media",
    "event_types": ["media.played"],
    "measure": {"kind": "sum", "field": "minutes"},
}


def service() -> DefinitionService:
    types = EventTypeRegistry()
    types.register(EventType("media.played", "t", aggregatable=frozenset({"minutes", "genre"})))
    types.register(EventType("media.rated", "t", aggregatable=frozenset({"genre"})))
    return DefinitionService(None, OutboxEventPublisher(), None, types, StatisticsConfig)  # type: ignore[arg-type]


def test_closed_schema() -> None:
    defs = service()
    assert defs.parse(BASE).measure.kind == "sum"
    for change, fragment in (
        ({"event_types": ["media.unknown"]}, "unknown event type"),
        ({"dimensions": ["artist"]}, "not aggregatable"),
        ({"event_types": ["media.played", "media.rated"]}, "not aggregatable"),  # minutes not on media.rated
        ({"measure": {"kind": "sum", "field": "actor"}}, "numeric event field"),
        ({"measure": {"kind": "count", "field": "minutes"}}, "takes no field"),
        ({"min_cohort_size": 2}, "at least 5"),
    ):
        with pytest.raises(InvalidDefinition) as error:
            defs.parse({**BASE, **change})
        assert any(fragment in e for e in error.value.extensions["errors"]), (change, error.value.extensions)
    with pytest.raises(InvalidDefinition):
        defs.parse({**BASE, "measure": {"kind": "median", "field": "minutes"}})  # outside the closed set
    with pytest.raises(InvalidDefinition):
        defs.parse({**BASE, "sql": "SELECT 1"})  # no free expressions
    with pytest.raises(ValidationError):
        StatisticDefinition.model_validate(
            {**BASE, "filter": [{"field": "genre", "op": "regex", "value": ".*"}]}
        )


def test_periods() -> None:
    wednesday = date(2026, 10, 7)
    assert resolve(Period("day"), today=wednesday) == (wednesday, wednesday)
    assert resolve(Period("week"), today=wednesday) == (date(2026, 10, 5), date(2026, 10, 11))
    assert resolve(Period("week"), today=wednesday, first_day_of_week=6) == (
        date(2026, 10, 4),
        date(2026, 10, 10),
    )
    assert resolve(Period("month"), today=date(2026, 2, 14)) == (date(2026, 2, 1), date(2026, 2, 28))
    assert resolve(Period("quarter"), today=date(2026, 11, 3)) == (date(2026, 10, 1), date(2026, 12, 31))
    assert resolve(Period("year"), today=wednesday) == (date(2026, 1, 1), date(2026, 12, 31))
    assert resolve(Period("last_n_days", days=7), today=wednesday) == (date(2026, 10, 1), wednesday)
    assert resolve(Period("month", anchor=date(2026, 3, 29)), today=wednesday) == (
        date(2026, 3, 1),
        date(2026, 3, 31),
    )
    assert previous(date(2026, 10, 1), date(2026, 10, 7)) == (date(2026, 9, 24), date(2026, 9, 30))
    with pytest.raises(PeriodInvalid):
        resolve(Period("custom", start=date(2026, 2, 1), end=date(2026, 1, 1)), today=wednesday)
    with pytest.raises(PeriodInvalid):
        resolve(Period("last_n_days", days=0), today=wednesday)


def test_trend() -> None:
    up = trend(15, 10)
    assert up is not None and (up.direction, up.delta, up.percent) == ("up", 5, 50.0)
    from_nothing = trend(4, 0)
    assert from_nothing is not None and from_nothing.percent is None  # no misleading percentage
    assert trend(3, 3).direction == "flat" and trend(None, 3) is None  # type: ignore[union-attr]


def test_suppression_prevents_differencing() -> None:
    cells = [Cell({"g": "a"}, 50, 20), Cell({"g": "b"}, 9, 6), Cell({"g": "c"}, 2, 1)]
    out = PrivacyGuard.suppress(cells, 5)
    assert out == [{"dims": {"g": "a"}, "value": 50}, {"dims": {"__other__": "other"}, "value": 11}]
    assert PrivacyGuard.suppress([Cell({"g": "a"}, 3, 3)], 5) == []


def test_pack_registry_owner() -> None:
    packs = PackRegistry()
    packs.register("media", [BASE], owner="module:media")
    packs.register("radio", [{**BASE, "key": "plugin_radio.minutes"}], owner="plugin:radio")
    with pytest.raises(DefinitionError):
        packs.register("radio", [{**BASE, "key": "media.stolen"}], owner="plugin:radio")
    assert [(d.key, active) for d, _, active in packs.definitions()] == [
        ("media.minutes", True),
        ("plugin_radio.minutes", False),
    ]
    assert packs.unregister("plugin:radio") == 1 and len(packs.definitions()) == 1
