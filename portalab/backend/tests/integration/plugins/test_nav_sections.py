"""027 T040 — a plugin's navigation lands in the section it declares (``plugin-<key>``), with its entry keyed
``plugin.<key>.…``; disabling the plugin removes the entry and the section together."""

import pytest

from tests.integration.plugins.conftest import PlHarness

pytestmark = pytest.mark.integration


async def test_plugin_section_and_entry(pl: PlHarness) -> None:
    await pl.installed(pl.hello())
    navigation = pl.registries.navigation
    entry = navigation.get("plugin.hello.home")
    assert entry is not None and entry.group == "plugin-hello"
    section = navigation.section("plugin-hello")
    assert section is not None and section.owner == "plugin:hello"
    assert navigation.section_for(entry) == "plugin-hello"
    assert not [r for r in navigation.rejections if r.owner == "plugin:hello"]
    navigation.unregister("plugin:hello")
    assert navigation.get("plugin.hello.home") is None and navigation.section("plugin-hello") is None
