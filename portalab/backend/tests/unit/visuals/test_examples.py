"""028 (US8, T093): every example pack of ``examples/visual-packs`` passes the analysis — nothing blocking,
nothing to warn about — so authors can start from any of them (030: a look of a kind an example plugin adds,
with that plugin enabled)."""

import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

from portalab.capabilities.visuals import PluginVisualType, plugin_visual_types
from portalab.modules.visuals.analysis import analyse
from portalab.modules.visuals.store import read_folder
from tests.unit.visuals.support import FakeInterfaces

EXAMPLES = Path(__file__).resolve().parents[4] / "examples" / "visual-packs"
PLUGINS = EXAMPLES.parent / "plugins"


@pytest.fixture(autouse=True)
def example_plugins() -> Iterator[None]:
    """The kinds of visuals the example plugins declare, as when they are enabled."""
    owners = []
    for manifest in sorted(PLUGINS.glob("*/plugin.toml")):
        raw = tomllib.loads(manifest.read_text())
        owner = f"plugin:{raw['key']}"
        for item in raw.get("capabilities", {}).get("visual_types", []):
            kind = PluginVisualType(f"{owner}.{item['key']}", owner, item["label_key"], icon=item.get("icon"))
            plugin_visual_types.register(kind)
            owners.append(owner)
    yield
    for owner in set(owners):
        plugin_visual_types.remove(owner)


@pytest.mark.parametrize("folder", sorted(p.name for p in EXAMPLES.iterdir() if (p / "pack.json").exists()))
def test_every_example_is_publishable(folder: str) -> None:
    report = analyse(read_folder(EXAMPLES / folder), interfaces=FakeInterfaces())
    assert report["summary"]["publishable"], folder
    assert [(i["code"], i["element"]) for i in report["items"] if i["level"] != "info"] == []


def test_the_examples_cover_every_kind_of_element_authors_may_bring() -> None:
    types = set()
    for folder in EXAMPLES.iterdir():
        if (folder / "pack.json").exists():
            types |= {
                e["type"] for e in analyse(read_folder(folder), interfaces=FakeInterfaces())["elements"]
            }
    assert {
        "theme",
        "navigation",
        "level_up",
        "avatar_frame",
        "booster_scene",
        "widget",
        "widget_option",
    } <= types


def test_the_workflow_journeys_fixtures_follow_the_analysis() -> None:
    """The e2e journey of the six steps (T020) walks reports the analysis really gives: regenerate them with
    ``uv run python scripts/e2e_visual_fixtures.py`` when the analysis changes."""
    import json

    fixtures = (
        Path(__file__).resolve().parents[4] / "frontend" / "tests" / "e2e" / "visual-packs" / "fixtures"
    )
    saved = json.loads((fixtures / "nordlys.json").read_text())["report"]
    fresh = analyse(read_folder(EXAMPLES / "nordlys"), interfaces=FakeInterfaces())
    assert saved["summary"] == fresh["summary"]
    assert [e["product"] for e in saved["elements"]] == [e["product"] for e in fresh["elements"]]
