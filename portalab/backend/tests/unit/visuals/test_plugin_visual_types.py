"""030 — a kind of visual a plugin adds (``plugin:messenger.bubble``): a pack bringing a look of it is refused
while no enabled plugin declares the kind, accepted once one does (its CSS held to its look like any look);
the shop product it makes is of the plugin's kind, its look under ``look``."""

from pathlib import Path

from portalab.capabilities.visuals import PluginVisualType, plugin_visual_types
from portalab.modules.visuals.analysis import analyse
from portalab.modules.visuals.service import VisualPacks
from portalab.modules.visuals.store import read_source as read_files

PACK = Path(__file__).resolve().parents[4] / "examples" / "visual-packs" / "messenger-bubbles"


def _codes(report: dict) -> set[str]:
    return {f["code"] for f in report.get("items", []) if f.get("level") == "blocking"}


def test_a_look_of_a_plugins_kind() -> None:
    files = read_files(PACK)
    assert "element.type" in _codes(analyse(files))  # nobody draws it
    plugin_visual_types.register(
        PluginVisualType("plugin:messenger.bubble", "plugin:messenger", "plugin.messenger:type.bubble")
    )
    try:
        report = analyse(files)
        assert not _codes(report), report.get("items")
        element = report["elements"][0]
        assert element["product"] == "messenger_bubble_aurora"
        product = VisualPacks.product_of(element, {})
        assert product["type"] == "plugin:messenger.bubble" and product["payload"] == {"look": "aurora"}
    finally:
        plugin_visual_types.remove("plugin:messenger")
