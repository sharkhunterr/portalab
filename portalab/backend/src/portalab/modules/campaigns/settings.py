"""Campaign settings (T002), declared to Administration."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:campaigns"


@dataclass(frozen=True, slots=True)
class CampaignsConfig:
    ending_soon_hours: int = 24
    max_active_campaigns: int = 10
    reconcile_seconds: int = 60
    default_timezone: str = "UTC"


SETTINGS: dict[str, str] = {
    "ending_soon_hours": "campaigns.endingSoonHours",
    "max_active_campaigns": "campaigns.maxActiveCampaigns",
    "reconcile_seconds": "campaigns.reconcileSeconds",
    "default_timezone": "campaigns.defaultTimezone",
}
_DESCRIPTIONS = {
    "ending_soon_hours": "Hours before the end of an occurrence when 'ending soon' is announced.",
    "max_active_campaigns": "Active campaigns above which the console warns (soft limit).",
    "reconcile_seconds": "Seconds between schedule reconciliations.",
    "default_timezone": "Time zone of new campaigns' schedules.",
}


def declare_campaign_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = CampaignsConfig()
    for name, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, name)
            declare(
                scope="global",
                key=key,
                schema=type(default),
                default=default,
                owner=OWNER,
                description=_DESCRIPTIONS[name],
            )


declare_campaign_settings()
