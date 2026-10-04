"""027 T030 — navigation sections: closed schema, first registration wins, plugin namespace, owner fallback,
withdrawal of an owner removes its sections with its entries."""

from portalab.capabilities.navigation import FALLBACK_SECTION, NavigationContribution, NavigationRegistry
from portalab.modules.shell.builtin import SECTIONS, register_builtin


def _entry(key: str, owner: str, group: str = "main") -> NavigationContribution:
    return NavigationContribution(
        key=key,
        owner=owner,
        kind="entry",
        label_key="x",
        route="/x",
        group=group,
        required_permission="users.self.manage",
    )


def test_closed_schema_and_first_wins() -> None:
    registry = NavigationRegistry()
    assert registry.register_section({"key": "games", "owner": "module:games", "label_key": "nav.games"})
    assert registry.register_section({"key": "games", "owner": "module:other", "label_key": "nav.x"}) is None
    evil = {"key": "x", "owner": "module:a", "label_key": "l", "css": "evil"}
    assert registry.register_section(evil) is None
    assert registry.register_section({"key": "Bad Key", "owner": "module:a", "label_key": "l"}) is None
    reasons = [(r.key, r.reason) for r in registry.drain_rejections()]
    assert reasons == [("section:games", "conflict"), ("section:x", "schema"), ("section:Bad Key", "schema")]


def test_plugin_sections_are_namespaced_and_withdrawn_with_their_owner() -> None:
    registry = NavigationRegistry()
    assert registry.register_section({"key": "radio", "owner": "plugin:radio", "label_key": "l"}) is None
    assert registry.register_section({"key": "plugin-radio", "owner": "plugin:radio", "label_key": "l"})
    registry.register(_entry("plugin.radio.home", "plugin:radio", group="plugin-radio"))
    assert registry.unregister("plugin:radio") == 1
    assert registry.section("plugin-radio") is None and registry.all() == []


def test_placement_falls_back_to_owner_default_then_more() -> None:
    registry = NavigationRegistry()
    register_builtin(registry)
    assert registry.section_for(_entry("media.extra", "module:media")) == "media"
    assert registry.section_for(_entry("support.x", "module:support", group="support")) == "support"
    assert registry.section_for(_entry("plugin.a.b", "plugin:a", group="nope")) == FALLBACK_SECTION


def test_builtin_sections_stay_within_the_limit() -> None:
    everyone = [s for s in SECTIONS if s["audience"] == "everyone" and s["key"] != FALLBACK_SECTION]
    assert len(everyone) + 1 <= 9  # + Administration
