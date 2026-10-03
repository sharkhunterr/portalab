"""Dashboard settings (T002), declared to Administration (CD-011). Widget policies and the starter layout
are validated dynamically against the registered widgets (``validators.py``)."""

from dataclasses import dataclass, field
from typing import Any

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:dashboard"
POLICIES = "dashboard.widgetPolicies"
STARTER = "dashboard.starterLayout"
POLICY_CLASSES: tuple[str, ...] = ("free", "default", "mandatory", "locked", "conditional", "disabled")

DEFAULT_STARTER: list[dict[str, Any]] = [
    {"widget_key": "dashboard.welcome", "w": 6, "h": 2},
    {"widget_key": "health.services_summary", "w": 6, "h": 2},
]


@dataclass(frozen=True, slots=True)
class DashboardConfig:
    widget_policies: dict[str, dict[str, Any]] = field(default_factory=dict)
    starter_layout: list[dict[str, Any]] = field(default_factory=lambda: [dict(i) for i in DEFAULT_STARTER])
    lookback_days: int = 30
    max_items: int = 20
    inactivity_gap_minutes: int = 30
    summary_types: list[str] = field(default_factory=list)  # empty: every registered type
    widget_timeout_ms: int = 5000


SETTINGS: dict[str, str] = {
    "widget_policies": POLICIES,
    "starter_layout": STARTER,
    "lookback_days": "dashboard.sinceLastLogin.lookbackDays",
    "max_items": "dashboard.sinceLastLogin.maxItems",
    "inactivity_gap_minutes": "dashboard.sinceLastLogin.inactivityGapMinutes",
    "summary_types": "dashboard.sinceLastLogin.types",
    "widget_timeout_ms": "dashboard.widgetTimeoutMs",
}

_SCHEMAS: dict[str, Any] = {
    "widget_policies": dict[str, dict[str, Any]],
    "starter_layout": list[dict[str, Any]],
    "lookback_days": int,
    "max_items": int,
    "inactivity_gap_minutes": int,
    "summary_types": list[str],
    "widget_timeout_ms": int,
}

_DESCRIPTIONS = {
    "widget_policies": "Per-widget policy: {key: {class: free|default|mandatory|locked|conditional|disabled, "
    "condition?, lockedConfig?}}.",
    "starter_layout": "Starter dashboard applied at onboarding: [{widget_key, w, h, roles?}].",
    "lookback_days": "How far back “Since last login” looks (days).",
    "max_items": "Maximum items shown in “Since last login”.",
    "inactivity_gap_minutes": "Minutes of inactivity after which “Since last login” starts a new period.",
    "summary_types": "Change types shown in “Since last login” (empty: all).",
    "widget_timeout_ms": "Time budget (ms) of each widget's data; a slower widget shows as unavailable.",
}


def declare_dashboard_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    defaults = DashboardConfig()
    for name, key in SETTINGS.items():
        if key not in known:
            declare(
                scope="global",
                key=key,
                schema=_SCHEMAS[name],
                default=getattr(defaults, name),
                owner=OWNER,
                description=_DESCRIPTIONS[name],
            )


declare_dashboard_settings()
