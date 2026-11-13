"""028: the demo catalog as a portal holds it once every pack is on — the demo shop's products
(``demo_catalog.json``) and the products of Portalab's own packs, rebuilt from their elements (economy,
texts, payload with the look's field) the way their synchronisation publishes them."""

import json
from functools import cache
from typing import Any

from portalab.app.demo_shop import SHOP
from portalab.capabilities.visuals import builtin_root
from portalab.modules.visuals.manifest import LOOK_FIELD
from portalab.modules.visuals.service import VisualPacks

ECONOMY_DEFAULTS: dict[str, Any] = {
    "price": None,
    "rarity": "common",
    "level": None,
    "supply": None,
    "collection": None,
    "icon": None,
    "repeatable": False,
    "season": None,
    "limit": None,
    "featured": False,
    "reward_only": False,
    "contribution": None,
}


@cache
def pack_products() -> tuple[dict[str, Any], ...]:
    root = builtin_root()
    assert root is not None
    out = []
    for file in sorted(root.glob("*/elements/*/element.json")):
        element = json.loads(file.read_text(encoding="utf-8"))
        if not element.get("product") or element.get("type") == "navigation":
            continue
        if (element.get("economy") or {}).get("sold") is False:
            continue  # offered to everyone: no shop product (issue 225: the candy wheel)
        payload = dict(element.get("payload") or {})
        field = LOOK_FIELD.get(element["type"])
        if field and element.get("look") is not None:
            payload[field] = element["look"]
        if element["type"] in ("widget", "widget_style", "widget_option"):
            # what a widget's look, option or own widget is sold as (``<widget>:<setting>=<value>``…)
            payload = VisualPacks.product_of({**element, "economy": element.get("economy") or {}}, {})[
                "payload"
            ]
        out.append(
            {
                **ECONOMY_DEFAULTS,
                **(element.get("economy") or {}),
                "key": element["product"],
                "type": element["type"],
                "names": element.get("names") or {},
                "descriptions": element.get("descriptions") or {},
                "payload": payload,
                "pack": file.parts[-4],
            }
        )
    return tuple(out)


def full_catalog() -> list[dict[str, Any]]:
    return [*SHOP, *pack_products()]
