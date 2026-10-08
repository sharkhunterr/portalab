"""027: a universe theme alone shows the free default looks; its ultimate pack holds the sold ones it uses
(notification style and entrance, ambience, celebration, level-up), so the pack really is the whole
universe."""

import json

import pytest

from portalab.app import demo_shop

FIELDS = {
    "notification_style": "style",
    "notification_animation": "animation",
    "ambient": "ambient",
    "effect": "effect",
    "level_up": "animation",
}


def _sold() -> dict[tuple[str, str], set[str]]:
    sold: dict[tuple[str, str], set[str]] = {}
    for product in demo_shop.SHOP:
        field = FIELDS.get(product["type"])
        if field and field in product["payload"]:
            sold.setdefault((product["type"], product["payload"][field]), set()).add(product["key"])
    return sold


@pytest.mark.parametrize("theme", sorted(demo_shop.UNIVERSES))
def test_ultimate_pack_holds_the_sold_looks_of_its_theme(theme: str) -> None:
    definition = json.loads((demo_shop.BUILTIN_THEMES / f"{theme}.json").read_text(encoding="utf-8"))
    wanted = {
        ("notification_style", definition.get("notification", {}).get("style")),
        ("notification_animation", definition.get("notification", {}).get("animation")),
        ("ambient", definition.get("background", {}).get("ambient")),
        ("effect", definition.get("motion", {}).get("celebration")),
        ("level_up", definition.get("motion", {}).get("levelUp")),
    }
    pack = next(p for p in demo_shop.SHOP if p["key"] == f"ultimate_{theme}")
    contents = set(pack["payload"]["products"])
    sold = _sold()
    missing = [
        f"{kind}={value}"
        for kind, value in wanted
        if (kind, value) in sold and not sold[(kind, value)] & contents
    ]
    assert not missing, f"ultimate_{theme} lacks {missing}"


def test_pack_contents_exist() -> None:
    keys = {p["key"] for p in demo_shop.SHOP}
    for product in demo_shop.SHOP:
        if product["type"] == "bundle":
            assert set(product["payload"]["products"]) <= keys, product["key"]
