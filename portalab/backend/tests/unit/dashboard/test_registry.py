"""009 T004/T038 — a valid definition registers; invalid schema/defaults, unknown template/condition,
inconsistent sizes and foreign plugin namespaces are rejected; a key has one owner; unregister keeps
nothing of the owner (023 sweep) while stored instances are untouched (the registry holds no rows)."""

import pytest

from portalab.capabilities.dashboard import Size, SizeLimits, WidgetRegistry, WidgetRegistryError
from tests.unit.dashboard.fakes import FakeWidget, definition


class Changes:
    kind = "fake"

    async def changes_since(self, *args: object) -> list[object]:
        return []


def test_valid_and_invalid_definitions() -> None:
    registry = WidgetRegistry()
    registry.register(definition("wiki.recent"), FakeWidget())
    assert registry.get("wiki.recent") is not None
    for bad in (
        definition("nodots"),
        definition("wiki.bad_schema", config_schema={"type": "nonsense"}),
        definition("wiki.bad_defaults", config_defaults={"limit": 99}),
        definition("wiki.bad_template", template="iframe"),
        definition("wiki.bad_condition", conditions=[{"type": "eval", "value": "1==1"}]),
        definition("wiki.bad_size", size=SizeLimits(default=Size(1, 1), min=Size(2, 1), max=Size(4, 2))),
    ):
        with pytest.raises(WidgetRegistryError):
            registry.register(bad, FakeWidget())
    with pytest.raises(WidgetRegistryError):
        registry.register(definition("wiki.recent", owner="module:other"), FakeWidget())


def test_plugin_widgets_are_namespaced_and_declarative() -> None:
    registry = WidgetRegistry()
    with pytest.raises(WidgetRegistryError, match="namespaced"):
        registry.register(definition("wiki.fake", owner="plugin:radio", template="stat"), FakeWidget())
    with pytest.raises(WidgetRegistryError, match="declarative"):
        registry.register(definition("plugin:radio.now", owner="plugin:radio"), FakeWidget())
    registry.register(definition("plugin:radio.now", owner="plugin:radio", template="stat"), FakeWidget())


def test_unregister_owner_removes_everything() -> None:
    registry = WidgetRegistry()
    registry.register(definition("plugin:radio.now", owner="plugin:radio", template="stat"), FakeWidget())
    registry.register(definition("plugin:radio.top", owner="plugin:radio", template="list"), FakeWidget())
    registry.register_summary(Changes(), owner="plugin:radio")  # type: ignore[arg-type]
    registry.register(definition("wiki.recent"), FakeWidget())
    assert registry.unregister_owner("plugin:radio") == 3
    assert [w.definition.key for w in registry.widgets()] == ["wiki.recent"] and registry.summaries() == []
    assert registry.unregister("wiki.recent") and not registry.unregister("wiki.recent")
