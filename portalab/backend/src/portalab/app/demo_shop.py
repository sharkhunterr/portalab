"""The demo shop (027, 028): the products of the demo catalog no visual pack holds — features, widgets and
their options, statistics, perks, requests (data: ``demo_catalog.json``).

Every look — its product, price, rarity, level, texts, the theme packs and boosters holding them — is its
pack's (``packs/builtin``): none is written here. The packs publish their products when they are switched on
(the demo seed switches every one on); the interfaces are read from them too (``builtin_interfaces``).
"""

import json
from pathlib import Path
from typing import Any

from portalab.capabilities.visuals import SOCLE, builtin_interfaces, interface_document
from portalab.modules.marketplace.products.sync import definition as sync_definition

Product = dict[str, Any]
_DATA = json.loads((Path(__file__).parent / "demo_catalog.json").read_text(encoding="utf-8"))

SHOP: list[Product] = list(_DATA["products"])
# 027: products taken out of the shop — archived (no longer sold, their option no longer offered)
RETIRED: tuple[str, ...] = tuple(_DATA["retired"])

# 028: the universes are the interfaces in a pack of their own (neither the socle nor the base collection)
UNIVERSE_THEMES = tuple(k for k, pack in builtin_interfaces().items() if pack not in (SOCLE, "portalab-base"))


def theme_definition(theme: str) -> dict[str, Any]:
    """An interface's definition, from its built-in pack."""
    return interface_document(theme)


COLLECTIONS: tuple[tuple[str, str, str, int], ...] = (
    ("ultimate", "Theme packs", "crown", 1),
    ("themes", "Interfaces", "palette", 3),
    ("packs", "Packs", "shop", 5),
    ("boosters", "Boosters", "sparkles", 6),
    ("halloween", "Halloween", "moon", 10),
    ("new_wave", "New Wave", "zap", 20),
    ("badges", "Badges", "star", 22),
    ("titles", "Titles", "trophy", 24),
    ("essentials", "Essentials", "star", 30),
    ("assistant", "Assistant", "brain", 32),  # issue 173: the assistant's capacities
    ("profile", "Profile", "user", 35),
    ("names", "Name styles", "feather", 36),
    ("backgrounds", "Animated backgrounds", "sparkles", 37),
    ("looks", "Notifications", "bell", 40),
    ("ambients", "Ambiences", "snowflake", 42),
    ("celebrations", "Celebrations", "party", 43),
    ("palettes", "Palettes", "palette", 45),
    ("widgets", "Widgets", "dashboard", 50),
    ("statistics", "Statistics", "chart", 52),
    ("levels", "Level badges and level-ups", "trophy", 41),
    ("rewards", "Achievement rewards", "gift", 60),
)

# a widget's look sold in a pack needs the widget itself in that pack (#30)
LOOK_NEEDS = {
    "opt_style_clock_analog": "widget_clock",
    "opt_style_countdown_flip": "widget_countdown",
    "opt_style_wall_kenburns": "widget_poster_wall",
}


def definition(product: Product) -> dict[str, Any]:
    """The catalog definition of a demo product (what ``Catalog.create``/``revise`` take)."""
    return sync_definition(product)
