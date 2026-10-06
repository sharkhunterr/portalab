"""Economy settings (T002), declared to Administration."""

from dataclasses import dataclass, field
from typing import Any

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:gamification"


@dataclass(frozen=True, slots=True)
class EconomyConfig:
    max_total_boost: float = 5.0
    manual_grant_confirm_threshold: int = 1000
    anomaly_max_grants_per_hour: int = 60
    anomaly_max_coins_per_day: int = 1000
    anomaly_escalate_to_incident: bool = False
    timezone: str = "UTC"
    leaderboard_metrics: list[str] = field(
        default_factory=lambda: ["xp", "level", "contribution", "achievements"]
    )
    leaderboard_refresh_minutes: int = 15
    leaderboard_include_coins: bool = False
    withheld_retention_days: int = 90
    level_curve_active: int = 0  # 0: the latest published curve
    contribution_amount: int = 10
    # 027: play streaks — consecutive days with one of these events multiply their rewards
    streak: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": False,
            "event_types": ["media.playback_finished"],
            "values": ["xp"],
            "tiers": [{"days": 2, "multiplier": 1.5}, {"days": 5, "multiplier": 2.0}],
        }
    )
    # 027: what reaching a level gives — Coins, Contribution, a shop product offered — per tier
    level_rewards: list[dict[str, Any]] = field(default_factory=list)
    # 027: the overall pace — one factor on every rule's gains, set from the progression curve
    pace: dict[str, Any] = field(default_factory=lambda: {"factor": 1.0, "values": ["xp"]})


SETTINGS: dict[str, str] = {
    "max_total_boost": "economy.maxTotalBoost",
    "manual_grant_confirm_threshold": "economy.manualGrantConfirmThreshold",
    "anomaly_max_grants_per_hour": "economy.anomaly.maxGrantsPerHour",
    "anomaly_max_coins_per_day": "economy.anomaly.maxCoinsPerDay",
    "anomaly_escalate_to_incident": "economy.anomaly.escalateToIncident",
    "timezone": "economy.timezone",
    "leaderboard_metrics": "economy.leaderboards.metrics",
    "leaderboard_refresh_minutes": "economy.leaderboards.refreshMinutes",
    "leaderboard_include_coins": "economy.leaderboards.includeCoins",
    "withheld_retention_days": "economy.withheldRetentionDays",
    "level_curve_active": "economy.levelCurve.active",
    "contribution_amount": "economy.contribution.amount",
    "streak": "economy.streak",
    "level_rewards": "economy.levelRewards",
    "pace": "economy.pace",
}
_DESCRIPTIONS = {
    "max_total_boost": "Maximum combined multiplier (rule x campaign modifiers).",
    "manual_grant_confirm_threshold": "Manual grants at or above this amount need a confirmation.",
    "anomaly_max_grants_per_hour": "Grants per user per hour above which rewards are withheld for review.",
    "anomaly_max_coins_per_day": "Coins per user per day above which rewards are withheld for review.",
    "anomaly_escalate_to_incident": "Also open an incident when an economy anomaly is flagged.",
    "timezone": "Time zone of economy periods (days, weeks).",
    "leaderboard_metrics": "Leaderboard metrics offered.",
    "leaderboard_refresh_minutes": "Minutes between leaderboard snapshots.",
    "leaderboard_include_coins": "Offer a Coins leaderboard.",
    "withheld_retention_days": "Days withheld rewards are kept after review.",
    "level_curve_active": "Level curve version in force (0: the latest).",
    "contribution_amount": "Contribution granted for a recognised contribution (e.g. a converted report).",
    "streak": "Play streaks: {enabled, event_types, values, tiers: [{days, multiplier}]}.",
    "level_rewards": "Level rewards: [{level, coins, contribution, product, label}].",
    "pace": "Overall pace: {factor, values} — multiplies every rule's gains of these values.",
}


def declare_economy_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = EconomyConfig()
    schemas: dict[str, Any] = {
        "leaderboard_metrics": list[str],
        "streak": dict[str, Any],
        "level_rewards": list[dict[str, Any]],
        "pace": dict[str, Any],
    }
    for name, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, name)
            declare(
                scope="global",
                key=key,
                schema=schemas.get(name, type(default)),
                default=default,
                owner=OWNER,
                description=_DESCRIPTIONS[name],
            )


declare_economy_settings()
