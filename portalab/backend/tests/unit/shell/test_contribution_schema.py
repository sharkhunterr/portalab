"""004 T004/T037 — closed contribution schema, namespaces, duplicates, upgrader hook, owner withdrawal."""

import pytest

from portalab.capabilities.navigation import NavigationRegistry
from portalab.capabilities.navigation.contribution import register_upgrader, upgrade_raw

BASE = {
    "key": "media.library",
    "owner": "module:media",
    "kind": "entry",
    "label_key": "nav.media",
    "route": "/media",
    "required_permission": "media.read",
}


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"colour": "red"}, "extra"),
        ({"required_permission": ""}, "permission"),
        ({"key": "other.library"}, "namespaced"),
        ({"route": "https://evil.example"}, "route"),
        ({"kind": "related_link", "target_entry_key": None}, "target"),
    ],
)
def test_invalid_contributions_are_rejected(change: dict[str, object], reason: str) -> None:
    registry = NavigationRegistry()
    assert registry.register({**BASE, **change}) is None
    [rejection] = registry.rejections
    assert rejection.reason == "schema" and rejection.key == str({**BASE, **change}["key"])


def test_plugin_keys_are_namespaced() -> None:
    registry = NavigationRegistry()
    assert registry.register({**BASE, "owner": "plugin:radio", "key": "media.library"}) is None
    assert registry.register({**BASE, "owner": "plugin:radio", "key": "plugin.radio.player"}) is not None


def test_duplicates_rejected_deterministically() -> None:
    registry = NavigationRegistry()
    first = registry.register(BASE)
    assert registry.register(BASE) is first  # identical re-registration is idempotent
    assert registry.register({**BASE, "label_key": "nav.other"}) is None
    assert registry.rejections[-1].reason == "duplicate"
    assert (
        registry.register({**BASE, "owner": "plugin:media", "key": "media.library"}) is None
    )  # not namespaced
    assert registry.get("media.library") == first


def test_upgrader_hook() -> None:
    register_upgrader(0, lambda raw: {**raw, "label_key": raw.pop("label")})
    upgraded = upgrade_raw(
        {**{k: v for k, v in BASE.items() if k != "label_key"}, "label": "nav.media", "schema_version": 0}
    )
    assert upgraded["label_key"] == "nav.media" and upgraded["schema_version"] == 1


def test_unregister_owner() -> None:
    registry = NavigationRegistry()
    registry.register(BASE)
    registry.register({**BASE, "key": "media.requests", "route": "/media/requests"})
    registry.register({**BASE, "owner": "plugin:radio", "key": "plugin.radio.player", "route": "/radio"})
    version = registry.version
    assert registry.unregister("module:media") == 2
    assert [c.key for c in registry.all()] == ["plugin.radio.player"] and registry.version > version
