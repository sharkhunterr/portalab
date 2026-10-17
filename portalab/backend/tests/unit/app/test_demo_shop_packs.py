"""027: a universe theme alone shows the free default looks; its ultimate pack holds the sold ones it uses
(notification style and entrance, ambience, celebration, level-up), so the pack really is the whole
universe."""

import collections

import pytest

from portalab.app import demo_shop
from tests.catalog_fixtures import full_catalog

# 028: the catalog is the demo shop's products and the packs' — its design, frozen in them (#108)
GREAT_TIERS = (10, 20, 30, 40, 50)
EARLY = {"ultimate_nova": 5, "pack_nova": 5, "theme_nova": 5}
USEFUL = {
    "early_unlock",
    "access",
    "service_access",
    "widget",
    "statistic",
    "media_rescue",
    "special_request",
    "streak_freeze",
    "xp_boost",
    "project_launch",
    "profile_backdrop",
}
CATALOG = full_catalog()

FIELDS = {
    "notification_style": "style",
    "notification_animation": "animation",
    "ambient": "ambient",
    "effect": "effect",
    "level_up": "animation",
}


def _sold() -> dict[tuple[str, str], set[str]]:
    sold: dict[tuple[str, str], set[str]] = {}
    for product in CATALOG:
        field = FIELDS.get(product["type"])
        if field and field in product["payload"]:
            sold.setdefault((product["type"], product["payload"][field]), set()).add(product["key"])
    return sold


@pytest.mark.parametrize("theme", sorted(demo_shop.UNIVERSE_THEMES))
def test_ultimate_pack_holds_the_sold_looks_of_its_theme(theme: str) -> None:
    definition = demo_shop.theme_definition(theme)
    wanted = {
        ("notification_style", definition.get("notification", {}).get("style")),
        ("notification_animation", definition.get("notification", {}).get("animation")),
        ("ambient", definition.get("background", {}).get("ambient")),
        ("effect", definition.get("motion", {}).get("celebration")),
        ("level_up", definition.get("motion", {}).get("levelUp")),
    }
    pack = next(p for p in CATALOG if p["key"] == f"ultimate_{theme}")
    contents = set(pack["payload"]["products"])
    sold = _sold()
    missing = [
        f"{kind}={value}"
        for kind, value in wanted
        if (kind, value) in sold and not sold[(kind, value)] & contents
    ]
    assert not missing, f"ultimate_{theme} lacks {missing}"


def test_pack_contents_exist() -> None:
    keys = {p["key"] for p in CATALOG}
    for product in CATALOG:
        if product["type"] == "bundle":
            assert set(product["payload"]["products"]) <= keys, product["key"]


def test_every_demo_product_is_a_valid_definition() -> None:
    """#89: one invalid product (a key with a hyphen) stopped the whole demo catalogue half-way — the theme
    packs after it were never created."""
    from portalab.modules.marketplace.products.definition import parse_product

    for product in demo_shop.SHOP:  # the packs' products are analysed with their pack
        parse_product(demo_shop.definition(product))


def test_no_two_demo_products_share_a_key() -> None:
    """#89: a look made twice (the same title in a season and a universe) was silently created once."""
    keys = collections.Counter(product["key"] for product in CATALOG)
    assert [key for key, count in keys.items() if count > 1] == []


def test_levels_spread_over_the_whole_curve() -> None:
    """#108: a level gates a fifth of what is sold — the rarest looks, the dearest boosters, what serves —
    and reaches the highest level: every level from 3 to 50 unlocks something, a tier more than a level in
    between, a great tier (10, 20…) most; legendary things unlock on the great tiers only."""
    sold = [p for p in CATALOG if not p["reward_only"] and p["key"] not in demo_shop.RETIRED]
    gated = [p for p in sold if p["level"]]
    assert abs(len(gated) - len(sold) / 5) <= 2
    assert {p["level"] for p in gated if p["type"] not in USEFUL} >= set(range(3, 51))
    early = set(EARLY)
    assert {p["level"] for p in gated if p["rarity"] == "legendary" and p["key"] not in early} <= set(
        GREAT_TIERS
    )
    # the Nova universe, offered at level 5, is usable there: nothing in it asks for more
    by_key = {p["key"]: p for p in CATALOG}
    nova = by_key["ultimate_nova"]
    assert nova["level"] == 5
    assert all((by_key[k]["level"] or 0) <= 5 for k in nova["payload"]["products"])
    epic = collections.Counter(p["level"] for p in gated if p["rarity"] == "epic")
    assert epic[23] >= 2 * epic[22] and epic[20] > epic[23]  # Or I, the level before it, Argent III
    useful = {p["key"]: p["level"] for p in gated if p["type"] in USEFUL}
    assert useful["release_search"] == 20 and useful["request_tv_channel"] == 20
    assert {p["key"]: p["level"] for p in sold if p["type"] == "booster" and p["level"]} == {
        "booster_prestige": 15,
        "booster_legend": 30,
        "booster_celestial": 5,  # #130: the cosmos' own
    }
