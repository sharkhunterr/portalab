"""Dashboard settings (T002), declared to Administration (CD-011). Widget policies and the starter layout
are validated dynamically against the registered widgets (``validators.py``)."""

from dataclasses import dataclass, field
from typing import Any

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:dashboard"
POLICIES = "dashboard.widgetPolicies"
STARTER = "dashboard.starterLayout"
POLICY_CLASSES: tuple[str, ...] = (
    "free",
    "default",
    "mandatory",
    "locked",
    "pinned",
    "conditional",
    "disabled",
)

# 027: what matters to everyone sits pinned on the first row — incidents and the current campaign, one line
# each
DEFAULT_POLICIES: dict[str, dict[str, Any]] = {
    "support.open_incidents": {
        "class": "pinned",
        "x": 0,
        "y": 0,
        "w": 6,
        "h": 1,
        "move": True,
        "resize": True,
    },
    "campaigns.active": {"class": "pinned", "x": 6, "y": 0, "w": 6, "h": 1},
}

# 027: a first visit — free widgets only (nothing to buy first), in rows of 12 columns that fit together
# (each row's widgets share a height; widgets a member cannot use yet are skipped). Under the pinned line
# (incidents · campaign, one row each): a glance line (shortcuts, my level, today's objectives, compact),
# what is new for me beside a title drawn at random, what I was watching, what came in, the services and
# the news, the community and the calendar, my statistics and my tickets, the shop window and the links;
# what a new member has nothing in yet (watching, statistics) stays out of sight until it fills up
DEFAULT_STARTER: list[dict[str, Any]] = [
    {"widget_key": "dashboard.welcome", "w": 6, "h": 1},
    {"widget_key": "gamification.progress", "w": 3, "h": 1},
    {"widget_key": "gamification.daily_objectives", "w": 3, "h": 1},
    {"widget_key": "dashboard.since_last_visit", "w": 8, "h": 3},
    {"widget_key": "media.shuffle", "w": 4, "h": 3},
    {"widget_key": "media.continue", "w": 12, "h": 3, "config": {"_hide_empty": True}},
    {"widget_key": "media.recently_added", "w": 12, "h": 3},
    {"widget_key": "health.services_summary", "w": 6, "h": 3},
    {"widget_key": "news.latest", "w": 6, "h": 3},
    {"widget_key": "community.activity", "w": 6, "h": 3},
    {"widget_key": "calendar.month", "w": 6, "h": 3},  # 3 rows: this week and what comes
    {"widget_key": "support.my_tickets", "w": 6, "h": 3},
    {"widget_key": "marketplace.featured", "w": 6, "h": 3},
    # alone on their rows: a widget waiting to fill up leaves no hole beside it
    {"widget_key": "media.stats", "w": 12, "h": 3, "config": {"_hide_empty": True}},
    {"widget_key": "health.service_links", "w": 12, "h": 2},
]


@dataclass(frozen=True, slots=True)
class DashboardConfig:
    widget_policies: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_POLICIES.items()}
    )
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
    "widget_policies": "Per-widget policy: {key: {class: free|default|mandatory|locked|pinned|conditional|"
    "disabled, condition?, lockedConfig?, x?, y?, w?, h?, move?, resize? (pinned)}}.",
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
