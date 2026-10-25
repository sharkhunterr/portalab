"""Issue 253 — a portal's game setup as a whole, taken from one portal and applied to another: its shop,
what earns XP and Coins (the reward rules), the level curve, the rewards by level, the achievements, the
quests, the campaigns, and the play settings (streak, pace, bonuses, the wheel, the contribution, the
leaderboards).

The shop keeps where each product comes from: Portalab's own catalog (features, widgets, statistics, perks —
``demo_catalog.json``) is published as Portalab defines it; the products of visual packs stay their packs' —
the setup names the packs to switch on (Portalab's own) or to install (the examples Portalab ships, extensions
like any other), never their products; only the products the administrators made themselves (boosters, card
boosters…) are carried, with the scene each booster wears. A product already in the shop is left as its
administrators set it.

It spans two modules (gamification, campaigns), so it lives here, beside the demo seed, and goes through each
module's own services (validated, versioned, audited like an administrator's edits). Members' own state —
balances, progress, ledgers — is never part of it. Applying is idempotent: what is already the same is left
as it is, and each item that cannot be applied (a product the shop does not sell, a campaign key taken) is
said, never fatal to the rest.

Portalab ships one setup, the LAN's (``game_presets/lan.json``, captured by
``scripts/export-game-preset.py``): the arrival wizard offers it as is, or as a start to customise.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from portalab.app.demo_shop import COLLECTIONS, SHOP
from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.visuals import LOOK_TYPES, examples_root, live_looks
from portalab.core.authz_port import Principal
from portalab.core.time import utc_now
from portalab.modules.gamification.achievements.definition import parse_achievement
from portalab.modules.gamification.quests.definition import parse_quest
from portalab.modules.gamification.rules.definition import parse_rule
from portalab.modules.gamification.settings import SETTINGS, EconomyConfig
from portalab.modules.marketplace.products.service import Catalog
from portalab.modules.marketplace.products.sync import sync_product
from portalab.modules.visuals.manifest import ManifestError, parse_pack

FORMAT = "portalab.game"
VERSION = 2  # 2: the shop
PRESETS = ("lan",)
# the play settings a setup carries (the operations' own — anomaly thresholds, retention — stay the portal's)
CARRIED = (
    "streak",
    "level_rewards",
    "reward_bonuses",
    "pace",
    "wheel",
    "contribution_amount",
    "max_total_boost",
    "leaderboard_metrics",
    "leaderboard_include_coins",
)
LIVE_CAMPAIGNS = ("draft", "scheduled", "active", "paused")
# the shop first: the rewards by level, the achievements and the campaigns name its products
PARTS = ("shop", "settings", "curve", "rules", "achievements", "quests", "campaigns")
ACCESS_PERMISSIONS = "marketplace.access.allowedPermissions"


def preset(key: str) -> dict[str, Any]:
    if key not in PRESETS:
        raise KeyError(key)
    return dict(json.loads((Path(__file__).parent / "game_presets" / f"{key}.json").read_text("utf-8")))


def counts(setup: Mapping[str, Any]) -> dict[str, int]:
    shop = setup.get("shop") or {}
    return {
        "catalog": len(SHOP) if shop.get("catalog") else 0,
        "packs": len(shop.get("packs") or []),
        "products": len(shop.get("products") or []),
        "settings": len(setup.get("settings") or {}),
        "rules": len(setup.get("rules") or []),
        "achievements": len(setup.get("achievements") or []),
        "quests": len(setup.get("quests") or []),
        "campaigns": len(setup.get("campaigns") or []),
        "level_rewards": len((setup.get("settings") or {}).get(SETTINGS["level_rewards"]) or []),
    }


async def export(platform: Any) -> dict[str, Any]:
    """The portal's game setup as it stands (the play settings an administrator changed, the published
    definitions of its own — not those a campaign or an extension brings)."""
    gamification, campaigns = platform.gamification, platform.campaigns
    now = utc_now(gamification.clock)
    default = EconomyConfig()
    settings = {
        SETTINGS[name]: getattr(gamification.config, name)
        for name in CARRIED
        if getattr(gamification.config, name) != getattr(default, name)
    }
    curve = await gamification.levels.curve()
    rules = [
        {"key": rule.key, "definition": rule.definition}
        for rule in await gamification.rules.latest()
        if rule.status == "active"
    ]
    achievements = [
        {"key": d.key, "definition": d.definition.model_dump(mode="json")}
        for d in await gamification.achievements.definitions(now)
        if not d.source_ref
    ]
    quests = [
        {"key": q.key, "definition": q.definition.model_dump(mode="json")}
        for q in await gamification.quests.definitions(now)
        if not q.source_ref
    ]
    live = []
    for campaign in await campaigns.definitions.all():
        if campaign.state not in LIVE_CAMPAIGNS:
            continue
        _, definition = await campaigns.definitions.get(campaign.id)
        live.append({"key": campaign.key, "definition": definition.model_dump(mode="json")})
    return {
        "format": FORMAT,
        "version": VERSION,
        "settings": settings,
        "curve": {"kind": "power", "base": curve.base, "exponent": curve.exponent},
        "rules": sorted(rules, key=lambda r: r["key"]),
        "achievements": sorted(achievements, key=lambda a: a["key"]),
        "quests": sorted(quests, key=lambda q: q["key"]),
        "campaigns": sorted(live, key=lambda c: c["key"]),
        "shop": await _export_shop(platform),
    }


def examples() -> dict[str, Path]:
    """The example packs Portalab ships: their id → their folder."""
    root = examples_root()
    out: dict[str, Path] = {}
    for folder in sorted(root.iterdir()) if root is not None and root.is_dir() else []:
        try:
            out[parse_pack((folder / "pack.json").read_bytes()).id] = folder
        except (OSError, ManifestError):
            continue
    return out


def _entry(product: Any, version: Any, collection: str | None) -> dict[str, Any]:
    """A product the administrators made, as the catalog's sync takes it."""
    return {
        "key": product.key,
        "type": product.type,
        "price": version.price_coins,
        "rarity": product.rarity,
        "names": dict(version.names),
        "descriptions": dict(version.descriptions),
        "payload": dict(version.payload),
        "collection": collection,
        "icon": product.icon,
        "featured": product.featured,
        "level": Catalog.min_level_of(version),
        "contribution": Catalog.min_contribution_of(version),
        "supply": product.supply,
        "limit": [product.limit_count, product.limit_days] if product.limit_count else None,
        "repeatable": product.repeatable,
        "reward_only": product.state == "unavailable",
        "config_required": version.config_required,
        "season": product.season,
        "refund_policy": dict(version.refund_policy),
    }


def _shown(product: Any, version: Any) -> bool:
    """A look sold by the administrators shows a look some pack has (else it is nothing to wear)."""
    field = LOOK_TYPES.get(product.type)
    return field is None or str(version.payload.get(field, "")) in live_looks.known(product.type)


async def _export_shop(platform: Any) -> dict[str, Any]:
    catalog: Catalog = platform.marketplace.catalog
    visuals = getattr(platform, "visuals", None)
    packs: list[str] = []
    held: frozenset[str] = frozenset()
    scenes: dict[str, dict[str, str]] = {}
    if visuals is not None:
        shipped = examples()
        packs = [
            p["id"]
            for p in await visuals.packs.listing()
            if p["state"] == "enabled" and not p["socle"] and (p["builtin"] or p["id"] in shipped)
        ]
        held = await visuals.packs.product_keys()
        scenes = {
            booster: {"pack": bound["pack"], "look": bound["look"]}
            for booster, bound in ((await visuals.packs.scene_bindings()).get("bindings") or {}).items()
        }
    base = {p["key"] for p in SHOP}
    categories = {c.id: c for c in await catalog.categories()}
    rows = await catalog.listing(states=("available", "unavailable"))
    made = [
        (product, version)
        for product, version in rows
        if product.key not in held
        and product.key not in base
        and product.extension_ref is None  # a plugin's own products are the plugin's
        and not product.type.startswith("plugin:")
        and _shown(product, version)
    ]
    used = {product.category_id for product, _ in made} - {None}
    known = {key for key, *_ in COLLECTIONS}
    return {
        "catalog": any(product.key in base for product, _ in rows),
        "packs": sorted(packs),
        "collections": sorted(
            (
                {"key": c.key, "label": c.label_key, "icon": c.icon, "position": c.position}
                for i, c in categories.items()
                if i in used and c.key not in known
            ),
            key=lambda c: c["key"],
        ),
        "products": sorted(
            (
                _entry(p, v, categories[p.category_id].key if p.category_id in categories else None)
                for p, v in made
            ),
            key=lambda e: e["key"],
        ),
        "scenes": dict(sorted(scenes.items())),
    }


class Report:
    def __init__(self) -> None:
        self.applied: dict[str, int] = dict.fromkeys(PARTS, 0)
        self.kept: dict[str, int] = dict.fromkeys(PARTS, 0)
        self.skipped: list[dict[str, str]] = []

    def skip(self, part: str, key: str, error: Exception | str) -> None:
        reason = error if isinstance(error, str) else getattr(error, "code", None) or type(error).__name__
        self.skipped.append({"part": part, "key": key, "reason": str(reason)})

    def out(self) -> dict[str, Any]:
        return {"applied": self.applied, "kept": self.kept, "skipped": self.skipped}


async def apply(
    platform: Any, actor: Principal, setup: Mapping[str, Any], parts: tuple[str, ...] = PARTS
) -> dict[str, Any]:
    if setup.get("format") != FORMAT or int(setup.get("version") or 0) > VERSION:
        raise ValueError("not a game setup this Portalab reads")
    report = Report()
    gamification = platform.gamification
    now = utc_now(gamification.clock)
    if "shop" in parts and setup.get("shop"):
        await _shop(platform, actor, dict(setup["shop"]), report)
    if "settings" in parts:
        await _settings(platform, actor, dict(setup.get("settings") or {}), report)
    if "curve" in parts and setup.get("curve"):
        current = await gamification.levels.curve()
        wanted = dict(setup["curve"])
        if (current.base, current.exponent) == (wanted.get("base"), wanted.get("exponent")):
            report.kept["curve"] += 1
        else:
            try:
                await gamification.levels.publish(wanted)
                report.applied["curve"] += 1
            except Exception as error:
                report.skip("curve", "curve", error)
    if "rules" in parts:
        await _rules(gamification, actor, setup.get("rules") or [], report)
    if "achievements" in parts:
        await _versioned(
            "achievements",
            gamification.achievements,
            actor,
            setup.get("achievements") or [],
            report,
            parse_achievement,
            {d.key: d.definition for d in await gamification.achievements.definitions(now)},
        )
    if "quests" in parts:
        await _versioned(
            "quests",
            gamification.quests,
            actor,
            setup.get("quests") or [],
            report,
            parse_quest,
            {q.key: q.definition for q in await gamification.quests.definitions(now)},
        )
    if "campaigns" in parts:
        await _campaigns(platform.campaigns, actor, setup.get("campaigns") or [], report)
    await platform.refresh_config()
    return report.out()


async def _shop(platform: Any, actor: Principal, shop: dict[str, Any], report: Report) -> None:
    catalog: Catalog = platform.marketplace.catalog
    if shop.get("catalog"):
        await _access_permissions(platform, actor, report)
        for key, label, icon, position in COLLECTIONS:
            await catalog.add_category(key, label, position, icon)
        for product in SHOP:
            await _product(catalog, actor, product, report)
    visuals = getattr(platform, "visuals", None)
    if visuals is not None:
        await _packs(visuals.packs, actor, [str(p) for p in shop.get("packs") or []], report)
    elif shop.get("packs"):
        report.skip("shop", "packs", "visual packs unavailable")
    for collection in shop.get("collections") or []:
        await catalog.add_category(
            str(collection["key"]),
            str(collection.get("label") or collection["key"]),
            int(collection.get("position") or 0),
            collection.get("icon"),
        )
    for product in shop.get("products") or []:
        await _product(catalog, actor, product, report)
    for booster, scene in (shop.get("scenes") or {}).items():
        if visuals is None:
            break
        bound = ((await visuals.packs.scene_bindings()).get("bindings") or {}).get(booster) or {}
        if (bound.get("pack"), bound.get("look")) == (scene.get("pack"), scene.get("look")):
            report.kept["shop"] += 1
            continue
        try:
            await visuals.packs.bind_scene(actor, str(booster), (str(scene["pack"]), str(scene["look"])))
            report.applied["shop"] += 1
        except Exception as error:
            report.skip("shop", f"scene {booster}", error)


async def _product(catalog: Catalog, actor: Principal, product: Mapping[str, Any], report: Report) -> None:
    """Created when the shop has none of this key; one it has stays as its administrators set it."""
    try:
        outcome = await sync_product(catalog, actor, {**product, "keep_existing": True})
    except Exception as error:
        report.skip("shop", str(product.get("key")), error)
        return
    if outcome == "created":
        report.applied["shop"] += 1
    else:
        report.kept["shop"] += 1


async def _packs(packs: Any, actor: Principal, wanted: list[str], report: Report) -> None:
    """Portalab's own packs switched on; the examples it ships installed (an extension like any other)."""
    listed = {p["id"]: p for p in await packs.listing()}
    shipped = examples()
    for pack in wanted:
        current = listed.get(pack)
        try:
            if current is not None and current["builtin"]:
                if current["state"] == "enabled":
                    report.kept["shop"] += 1
                    continue
                await packs.set_state(actor, pack, True)
            elif pack in shipped:
                if await packs.install_example(actor, shipped[pack]) == "kept":
                    report.kept["shop"] += 1
                    continue
            else:
                report.skip("shop", f"pack {pack}", "pack not shipped")
                continue
            report.applied["shop"] += 1
        except Exception as error:
            report.skip("shop", f"pack {pack}", error)


async def _access_permissions(platform: Any, actor: Principal, report: Report) -> None:
    """The permissions the catalog's « access » products grant, allowed for such products."""
    marketplace = platform.marketplace
    await marketplace.refresh_config()
    allowed = set(marketplace.config.access_allowed_permissions)
    wanted = sorted({str(p["payload"]["permission"]) for p in SHOP if p["type"] == "access"} | allowed)
    writers = marketplace.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if writers and set(wanted) != allowed:
        try:
            await writers[0].provider.set_global(actor, ACCESS_PERMISSIONS, wanted, reason="game setup")
            await marketplace.refresh_config()
        except Exception as error:
            report.skip("shop", ACCESS_PERMISSIONS, error)


async def _settings(platform: Any, actor: Principal, settings: dict[str, Any], report: Report) -> None:
    writers = platform.gamification.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if not writers:
        report.skip("settings", "*", "administration unavailable")
        return
    allowed = {SETTINGS[name] for name in CARRIED}
    level_rewards = SETTINGS["level_rewards"]
    if level_rewards in settings:
        settings[level_rewards] = await _sold_only(platform, settings[level_rewards], report)
    current = {SETTINGS[name]: getattr(platform.gamification.config, name) for name in CARRIED}
    for key, value in settings.items():
        if key not in allowed:
            report.skip("settings", key, "not a play setting")
            continue
        if current.get(key) == value:
            report.kept["settings"] += 1
            continue
        try:
            await writers[0].provider.set_global(actor, key, value, reason="game setup")
            report.applied["settings"] += 1
        except Exception as error:
            report.skip("settings", key, error)


async def _sold_only(platform: Any, rewards: Any, report: Report) -> list[dict[str, Any]]:
    """A level's reward keeps its Coins, XP and contribution; a product the shop does not sell is left out."""
    out = []
    for reward in rewards if isinstance(rewards, list) else []:
        reward = dict(reward)
        product = reward.get("product")
        if product:
            try:
                await platform.marketplace.catalog.get(str(product))
            except Exception:
                report.skip("settings", f"level {reward.get('level')}: {product}", "product not in this shop")
                reward["product"] = None
        out.append(reward)
    return out


async def _rules(gamification: Any, actor: Principal, rules: list[Any], report: Report) -> None:
    current = {r.key: r for r in await gamification.rules.latest()}
    for item in rules:
        key = str(item.get("key", ""))
        existing = current.get(key)
        try:
            if (
                existing is not None
                and existing.status == "active"
                and _same_rule(gamification, existing, item)
            ):
                report.kept["rules"] += 1
                continue
            rule = await gamification.rules.save(actor, key, item.get("definition") or {})
            await gamification.rules.publish(actor, key, rule.version)
            report.applied["rules"] += 1
        except Exception as error:
            report.skip("rules", key, error)


def _same_rule(gamification: Any, existing: Any, item: Mapping[str, Any]) -> bool:
    types = gamification.event_types
    return bool(parse_rule(existing.definition, types) == parse_rule(item.get("definition") or {}, types))


async def _versioned(
    part: str,
    service: Any,
    actor: Principal,
    items: list[Any],
    report: Report,
    parse: Any,
    current: Mapping[str, Any],
) -> None:
    for item in items:
        key = str(item.get("key", ""))
        try:
            if key in current and current[key] == parse(item.get("definition") or {}):
                report.kept[part] += 1
                continue
            await service.save(actor, key, item.get("definition") or {})
            report.applied[part] += 1
        except Exception as error:
            report.skip(part, key, error)


async def _campaigns(campaigns: Any, actor: Principal, items: list[Any], report: Report) -> None:
    existing = {c.key for c in await campaigns.definitions.all()}
    for item in items:
        key = str(item.get("key", ""))
        if key in existing:
            report.kept["campaigns"] += 1
            continue
        try:
            await campaigns.definitions.create(actor, key, item.get("definition") or {})
            report.applied["campaigns"] += 1
        except Exception as error:
            report.skip("campaigns", key, error)
    if report.applied["campaigns"]:
        await campaigns.reconciler.run()
