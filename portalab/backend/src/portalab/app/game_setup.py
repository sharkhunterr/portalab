"""Issue 253 — a portal's game setup as a whole, taken from one portal and applied to another: what earns XP
and Coins (the reward rules), the level curve, the rewards by level, the achievements, the quests, the
campaigns, and the play settings (streak, pace, bonuses, the wheel, the contribution, the leaderboards).

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

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.core.authz_port import Principal
from portalab.core.time import utc_now
from portalab.modules.gamification.achievements.definition import parse_achievement
from portalab.modules.gamification.quests.definition import parse_quest
from portalab.modules.gamification.rules.definition import parse_rule
from portalab.modules.gamification.settings import SETTINGS, EconomyConfig

FORMAT = "portalab.game"
VERSION = 1
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
PARTS = ("settings", "curve", "rules", "achievements", "quests", "campaigns")


def preset(key: str) -> dict[str, Any]:
    if key not in PRESETS:
        raise KeyError(key)
    return dict(json.loads((Path(__file__).parent / "game_presets" / f"{key}.json").read_text("utf-8")))


def counts(setup: Mapping[str, Any]) -> dict[str, int]:
    return {
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
