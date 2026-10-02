"""008 T036 — owner-tagged registrations: unregister(owner) removes every provider, resolver and action of
that owner (023 conformance sweep, F20); plugin kinds are namespaced; a kind has one owner."""

import pytest

from portalab.capabilities.search import ActionDef, SearchRegistry, SearchRegistryError
from tests.unit.search.fakes import FakeProvider, FakeResolver


def test_unregister_owner_removes_everything() -> None:
    registry = SearchRegistry()
    registry.register(FakeProvider("plugin:radio"), owner="plugin:radio")
    registry.register_resolver(FakeResolver("plugin:radio"), owner="plugin:radio")
    registry.register_action(ActionDef("plugin.radio.play", "x", "plugin:radio.use"), owner="plugin:radio")
    registry.register(FakeProvider("wiki"), owner="module:wiki")
    assert registry.unregister("plugin:radio") == 3
    assert [p.kind for p in registry.providers()] == ["wiki"]
    assert registry.resolvers() == [] and registry.actions() == []


def test_namespacing_and_single_owner() -> None:
    registry = SearchRegistry()
    with pytest.raises(SearchRegistryError):
        registry.register(FakeProvider("wiki"), owner="plugin:evil")
    registry.register(FakeProvider("wiki"), owner="module:wiki")
    with pytest.raises(SearchRegistryError):
        registry.register(FakeProvider("wiki"), owner="module:other")
