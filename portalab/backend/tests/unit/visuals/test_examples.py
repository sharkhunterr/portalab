"""028 (US8, T093): every example pack of ``examples/visual-packs`` passes the analysis — nothing blocking,
nothing to warn about — so authors can start from any of them."""

from pathlib import Path

import pytest

from portalab.modules.visuals.analysis import analyse
from portalab.modules.visuals.store import read_folder
from tests.unit.visuals.support import FakeInterfaces

EXAMPLES = Path(__file__).resolve().parents[4] / "examples" / "visual-packs"


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
