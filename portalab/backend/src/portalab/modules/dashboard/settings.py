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

# 027: what matters to everyone sits pinned on the first row — incidents and the current campaign; issue 186:
# a quarter each, my level and today's objectives beside them
DEFAULT_POLICIES: dict[str, dict[str, Any]] = {
    "support.open_incidents": {
        "class": "pinned",
        "x": 0,
        "y": 0,
        "w": 3,
        "h": 1,
        "move": True,
        "resize": True,
    },
    "campaigns.active": {"class": "pinned", "x": 3, "y": 0, "w": 3, "h": 1},
}

# 027: a first visit — free widgets only (nothing to buy first), in rows of 12 columns that fit together
# (each row's widgets share a height; widgets a member cannot use yet are skipped). Issue 12: what matters
# first, then the rest; what can be empty for a newcomer hides until it fills up (« _hide_empty ») and its
# neighbour takes its place. Issue 186: the administrator's own arrangement, kept as the default — on a
# computer the rows below, on a tablet (8 columns) and a phone (4) each widget's place of its own
# (``_on``: x, y, w, h), the pinned incidents and campaign derived on the first row of each.


def _on(*, phone: tuple[int, int, int, int], tablet: tuple[int, int, int, int]) -> dict[str, Any]:
    """A starter widget's places on a phone and a tablet (x, y, w, h)."""
    return {
        view: dict(zip(("x", "y", "w", "h"), at, strict=True))
        for view, at in (("phone", phone), ("tablet", tablet))
    }


DEFAULT_STARTER: list[dict[str, Any]] = [
    # a glance: my level, today's objectives (beside the pinned incidents and campaign), then the shortcuts
    {"widget_key": "gamification.progress", "w": 3, "h": 1, **_on(phone=(0, 1, 2, 1), tablet=(0, 1, 4, 1))},
    {
        "widget_key": "gamification.daily_objectives",
        "w": 3,
        "h": 1,
        **_on(phone=(2, 1, 2, 1), tablet=(4, 1, 4, 1)),
    },
    {"widget_key": "dashboard.welcome", "w": 12, "h": 1, **_on(phone=(0, 2, 4, 1), tablet=(0, 2, 8, 1))},
    # for me now: what I was watching, what is new for me, a title drawn at random
    {
        "widget_key": "media.continue",
        "w": 8,
        "h": 3,
        "config": {"_hide_empty": True},
        **_on(phone=(0, 3, 4, 3), tablet=(0, 3, 8, 3)),
    },
    # issue 225: the daily wheel beside it (its own look; packs' looks chosen in its settings)
    {
        "widget_key": "gamification.daily_wheel",
        "w": 4,
        "h": 3,
        **_on(phone=(0, 6, 4, 3), tablet=(0, 6, 8, 3)),
    },
    {
        "widget_key": "dashboard.since_last_visit",
        "w": 8,
        "h": 3,
        **_on(phone=(0, 9, 4, 3), tablet=(0, 9, 8, 3)),
    },
    {
        "widget_key": "media.shuffle",
        "w": 4,
        "h": 3,
        "config": {"_hide_empty": True},
        **_on(phone=(0, 12, 4, 3), tablet=(0, 12, 4, 3)),
    },
    # issue 185: the calendar high up and roomy — the whole month
    {"widget_key": "calendar.month", "w": 12, "h": 6, **_on(phone=(0, 15, 4, 6), tablet=(0, 15, 8, 6))},
    {
        "widget_key": "media.recently_added",
        "w": 12,
        "h": 3,
        "config": {"_hide_empty": True},
        **_on(phone=(0, 21, 4, 3), tablet=(0, 21, 8, 3)),
    },
    # issue 168: the homelab's radio — when one is connected
    {
        "widget_key": "media.radio",
        "w": 12,
        "h": 2,
        "config": {"_hide_empty": True},
        **_on(phone=(2, 24, 2, 2), tablet=(0, 24, 8, 2)),
    },
    # four quarter tiles; on a phone the services down the left, the radio and the shop window beside them,
    # then my tickets and the news
    {
        "widget_key": "health.services_summary",
        "w": 3,
        "h": 3,
        **_on(phone=(0, 24, 2, 5), tablet=(0, 26, 4, 3)),
    },
    {"widget_key": "marketplace.featured", "w": 3, "h": 3, **_on(phone=(2, 26, 2, 3), tablet=(4, 26, 4, 3))},
    {"widget_key": "support.my_tickets", "w": 3, "h": 3, **_on(phone=(0, 29, 2, 3), tablet=(0, 29, 4, 3))},
    {"widget_key": "news.latest", "w": 3, "h": 3, **_on(phone=(2, 29, 2, 3), tablet=(4, 29, 4, 3))},
    # what fills up with time: the community, my statistics (a hidden one gives its place to the other)
    {
        "widget_key": "community.activity",
        "w": 6,
        "h": 3,
        "config": {"_hide_empty": True},
        **_on(phone=(0, 32, 4, 3), tablet=(0, 32, 4, 3)),
    },
    {
        "widget_key": "media.stats",
        "w": 6,
        "h": 3,
        "config": {"_hide_empty": True},
        **_on(phone=(0, 35, 4, 2), tablet=(4, 32, 4, 3)),
    },
    {
        "widget_key": "health.service_links",
        "w": 12,
        "h": 1,
        "config": {"_hide_empty": True},
        **_on(phone=(0, 38, 4, 1), tablet=(0, 35, 8, 1)),
    },
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
