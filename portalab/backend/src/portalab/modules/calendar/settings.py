"""Calendar settings (T002)."""

from dataclasses import dataclass, field

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:calendar"


@dataclass(frozen=True, slots=True)
class CalendarConfig:
    source_timeout_ms: int = 2000
    max_range_days: int = 92
    reminder_lead_options: list[int] = field(default_factory=lambda: [15, 60, 1440])


SETTINGS = {
    "source_timeout_ms": "calendar.sourceTimeoutMs",
    "max_range_days": "calendar.maxRangeDays",
    "reminder_lead_options": "calendar.reminderLeadOptions",
}
_DESCRIPTIONS = {
    "source_timeout_ms": "How long the calendar waits for one source before showing it as unavailable.",
    "max_range_days": "Largest date range one calendar view may request.",
    "reminder_lead_options": "Reminder lead times users can choose (minutes before the item).",
}


def declare_calendar_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = CalendarConfig()
    schemas = {"reminder_lead_options": list[int]}
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


declare_calendar_settings()
