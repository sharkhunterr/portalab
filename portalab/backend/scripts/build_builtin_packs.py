"""Writes Portalab's own catalog as visual packs (spec 028, US2, slice B1): ``packs/builtin/<pack>/``.

Every look Portalab offers becomes an element of one built-in pack — its key, product, texts, economy and
contents kept exactly — drawn by its own files once they moved into the pack (slice B2:
``frontend/scripts/extract-builtin-packs.mjs`` writes ``look.css`` in the element's folder; kept here when the
packs are written again, the element drawn by it), else still by the portal's own code
(``render.renderer = "builtin"``). Packs:

- ``portalab-socle``: always on — the default interfaces, the looks no product sells (free for everyone) and
  the navigations the interface draws itself;
- ``portalab-<universe>``: one per universe — its interface and everything its « ultimate » pack holds;
- ``portalab-hd-<collection>``: the HD collections (their packs and what they hold, when no universe does);
- ``portalab-season-<season>``: the seasons' looks;
- ``portalab-base``: every other look — the « base collection ».

A product belongs to one pack only (the first that claims it, in that order); a pack of the shop may hold
products of other packs. Run from ``backend/``: ``uv run python scripts/build_builtin_packs.py [--out DIR]``.
"""

import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from portalab.app import demo_shop
from portalab.capabilities.visuals import shipped_looks
from portalab.modules.visuals.manifest import LOOK_FIELD

BACKEND = Path(__file__).resolve().parents[1]
OUT = BACKEND.parent / "packs" / "builtin"
LOCALES = BACKEND / "locales"
THEMES = BACKEND / "src" / "portalab" / "modules" / "ui" / "themes" / "builtin"
VERSION = "1.0.0"
VISUAL = {*LOOK_FIELD, "badge", "title", "bundle", "booster"} - {"profile_background", "widget_style"}
# where the interface names each type's looks (the same catalogs the SPA reads)
NAME_KEYS = {
    "level_up": ("notifications", "levelUp.names"),
    "effect": ("notifications", "universe.celebrations"),
    "ambient": ("notifications", "universe.ambients"),
    "avatar_frame": ("community", "looks.frame"),
    "profile_banner": ("community", "looks.banner"),
    "name_style": ("community", "looks.name"),
    "level_badge": ("notifications", "levelBadge.names"),
    "notification_style": ("notifications", "looks.styles"),
    "notification_animation": ("notifications", "looks.animations"),
    "palette": ("notifications", "palette.names"),
}
SEASONS = {
    "valentine": ("Valentine's Day", "Saint-Valentin"),
    "spring": ("Spring", "Printemps"),
    "summer": ("Summer", "Été"),
    "halloween": ("Halloween", "Halloween"),
    "christmas": ("Christmas", "Noël"),
}
ECONOMY = ("price", "rarity", "level", "supply", "collection", "icon", "repeatable", "season", "limit",
           "featured", "reward_only", "contribution")  # fmt: skip


def catalogs() -> dict[str, dict[str, dict[str, str]]]:
    out: dict[str, dict[str, dict[str, str]]] = {}
    for language in ("en", "fr"):
        out[language] = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in (LOCALES / language).glob("*.json")
        }
    return out


def look_names(texts: dict[str, Any], kind: str, look: str) -> dict[str, str]:
    namespace, prefix = NAME_KEYS.get(kind, ("", ""))
    names = {
        language: str(texts[language].get(namespace, {}).get(f"{prefix}.{look}", ""))
        for language in ("en", "fr")
    }
    return {language: name or look for language, name in names.items()}


def element_of(product: dict[str, Any], *, look_free: bool = True) -> dict[str, Any]:
    kind = product["type"]
    field = LOOK_FIELD.get(kind)
    payload = dict(product["payload"])
    look = payload.pop(field, None) if field and look_free else None
    economy = {k: product.get(k) for k in ECONOMY if product.get(k) not in (None, False)}
    if product.get("limit"):
        economy["limit"] = list(product["limit"])
    out: dict[str, Any] = {
        "type": kind,
        "product": product["key"],
        "names": product["names"],
        "descriptions": product["descriptions"],
        "render": {"kind": "renderer", "renderer": "builtin"},
        "economy": economy,
    }
    if look:
        out["look"] = look
    if payload:
        out["payload"] = payload
    return out


def build(out: Path) -> dict[str, int]:
    texts = catalogs()
    shop = [p for p in demo_shop.SHOP if p["type"] in VISUAL]
    by_key = {p["key"]: p for p in shop}
    owner: dict[str, str] = {}  # product → pack
    packs: dict[str, dict[str, Any]] = {}

    def pack(pack_id: str, en: str, fr: str, about_en: str, about_fr: str) -> dict[str, Any]:
        return packs.setdefault(
            pack_id,
            {
                "id": pack_id,
                "names": {"en": en, "fr": fr},
                "descriptions": {"en": about_en, "fr": about_fr},
                "products": [],
                "free": [],
            },
        )

    def claim(pack_id: str, key: str) -> None:
        if key in by_key and key not in owner:
            owner[key] = pack_id
            packs[pack_id]["products"].append(key)

    # universes: each « ultimate » pack and what it holds, its interface first
    for bundle in shop:
        held = bundle["payload"].get("products", []) if bundle["type"] == "bundle" else []
        theme = next((by_key[k] for k in held if by_key.get(k, {}).get("type") == "theme"), None)
        if not bundle["key"].startswith("ultimate_") or theme is None:
            continue
        universe = theme["payload"]["theme"]
        pack_id = f"portalab-{universe}"
        pack(
            pack_id,
            theme["names"]["en"].replace(" theme", ""),
            theme["names"]["fr"].replace("Thème ", "").replace("thème ", ""),
            f"The « {theme['names']['en']} » universe: its interface and everything its ultimate pack holds.",
            f"L'univers « {theme['names']['fr']} » : son interface et tout ce que contient son pack ultime.",
        )
        claim(pack_id, theme["key"])
        claim(pack_id, bundle["key"])
        for key in held:
            claim(pack_id, key)
    # the HD collections
    for bundle in shop:
        if not bundle["key"].startswith("pack_hd_"):
            continue
        pack_id = f"portalab-hd-{bundle['key'][len('pack_hd_') :].replace('_', '-')}"
        pack(
            pack_id,
            bundle["names"]["en"],
            bundle["names"]["fr"],
            "An HD collection: looks drawn by the graphics chip.",
            "Une collection HD : des looks dessinés par la carte graphique.",
        )
        claim(pack_id, bundle["key"])
        for key in bundle["payload"].get("products", []):
            claim(pack_id, key)
    # the seasons
    for product in shop:
        season = product.get("season") or (
            product["payload"].get("season") if product["type"] == "booster" else None
        )
        if season and product["key"] not in owner:
            en, fr = SEASONS.get(season, (season, season))
            pack(
                f"portalab-season-{season}", en, fr, f"The looks of {en}.", f"Les looks de la saison : {fr}."
            )
            claim(f"portalab-season-{season}", product["key"])
    # the base collection
    pack(
        "portalab-base",
        "Base collection",
        "Collection de base",
        "Portalab's looks that belong to no universe, season or HD collection.",
        "Les looks de Portalab qui n'appartiennent à aucun univers, saison ou collection HD.",
    )
    for product in shop:
        claim("portalab-base", product["key"])
    # the socle: default interfaces, free looks, the navigations the interface draws
    pack(
        "portalab-socle",
        "Portalab — socle",
        "Portalab — socle",
        "Always on: the default interfaces, the looks everyone wears, the built-in navigations.",
        "Toujours actif : les interfaces par défaut, les looks portés par tous, les navigations intégrées.",
    )
    sold: dict[str, set[str]] = defaultdict(set)
    for product in shop:
        field = LOOK_FIELD.get(product["type"])
        if field and product["payload"].get(field):
            sold[product["type"]].add(str(product["payload"][field]))
    # the looks no product sells: those the packs already hold (the packs are their source — none is listed in
    # the code), free in the socle
    free: list[dict[str, Any]] = []
    for kind, looks in shipped_looks(out).items():
        for look in dict.fromkeys(looks):
            if look in sold[kind]:
                continue
            names = look_names(texts, kind, look) if kind != "navigation" else {"en": look, "fr": look}
            free.append(
                {
                    "type": kind,
                    "look": look,
                    "names": names,
                    "render": {
                        "kind": "renderer",
                        "renderer": f"nav:{look}" if kind == "navigation" else "builtin",
                    },
                    "free": True,
                }
            )
    for path in sorted(THEMES.glob("*.json")):
        key = path.stem
        if key in sold["theme"]:
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        name = str(document.get("name") or key)
        free.append(
            {
                "type": "theme",
                "look": key,
                "names": {"en": name, "fr": name},
                "render": {"kind": "renderer", "renderer": "builtin"},
                "free": True,
            }
        )
    packs["portalab-socle"]["free"] = free

    # written: one folder per pack, one per element — the files a look brought (B2) kept, by folder
    kept: dict[str, dict[str, bytes]] = {}
    drawn: dict[str, dict[str, Any]] = {}  # how a look with files of its own is drawn (its element's render)
    if out.exists():
        for file in out.glob("*/elements/*/*"):
            if file.is_file() and file.name != "element.json":
                kept.setdefault(str(file.parent.relative_to(out)), {})[file.name] = file.read_bytes()
            elif file.is_file():
                render = json.loads(file.read_text(encoding="utf-8")).get("render") or {}
                if render.get("kind") != "renderer":
                    drawn[str(file.parent.relative_to(out))] = render
        shutil.rmtree(out)
    seen: set[tuple[str, str]] = set()
    counts: dict[str, int] = {}
    for pack_id, data in sorted(packs.items()):
        folder = out / pack_id
        (folder / "elements").mkdir(parents=True)
        elements = [*data["free"]]
        for key in data["products"]:
            product = by_key[key]
            field = LOOK_FIELD.get(product["type"])
            look = product["payload"].get(field) if field else None
            # a look two products sell: the first holds it, the other keeps it in its contents only
            first = look is None or (product["type"], str(look)) not in seen
            if look is not None:
                seen.add((product["type"], str(look)))
            elements.append(element_of(product, look_free=first))
        names: set[str] = set()
        contents = hashlib.sha256()
        for element in elements:
            base = (
                (element.get("product") or f"{element['type']}-{element['look']}").replace("_", "-").lower()
            )
            name = base[:48].rstrip("-")
            while name in names:
                name = f"{name[:44]}-{len(names) % 1000}"
            names.add(name)
            target = folder / "elements" / name
            target.mkdir()
            files = kept.get(str(target.relative_to(out)), {})
            for file_name, content in sorted(files.items()):
                (target / file_name).write_bytes(content)
                contents.update(file_name.encode() + content)
            if files and str(target.relative_to(out)) in drawn:
                element["render"] = drawn[str(target.relative_to(out))]
            (target / "element.json").write_text(json.dumps(element, ensure_ascii=False, indent=2) + "\n")
        # its version: the release's, and the content's fingerprint — a release changing a pack changes it
        digest = hashlib.sha256(
            json.dumps([data["names"], data["descriptions"], elements], sort_keys=True).encode()
            + contents.digest()
        ).hexdigest()[:10]
        manifest = {
            "format": 1,
            "id": pack_id,
            "version": f"{VERSION}+{digest}",
            "names": data["names"],
            "descriptions": data["descriptions"],
            "author": "Portalab",
            "license": "AGPL-3.0-or-later",
        }
        (folder / "pack.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        counts[pack_id] = len(elements)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    counts = build(args.out)
    print(f"{len(counts)} packs, {sum(counts.values())} elements → {args.out}")
    for pack_id, count in counts.items():
        print(f"  {pack_id}: {count}")


if __name__ == "__main__":
    main()
