"""Statistics settings (T002), declared to Administration (CD-011). Bucket boundaries use one statistics
time zone and first day of the week for everyone (deterministic values across consumers, R3)."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:statistics"
HIDDEN_SECTIONS = "statistics.hiddenSections"


@dataclass(frozen=True, slots=True)
class StatisticsConfig:
    timezone: str = ""  # empty: the portal default time zone (i18n.defaultTimeZone), else UTC
    first_day_of_week: int = 0  # 0 = Monday
    default_min_cohort_size: int = 5
    stale_after_seconds: int = 900
    max_buckets_per_request: int = 800
    bucket_retention_months: int = 36
    wrapped_enabled: bool = True


SETTINGS: dict[str, str] = {
    "timezone": "statistics.timezone",
    "first_day_of_week": "statistics.firstDayOfWeek",
    "default_min_cohort_size": "statistics.defaultMinCohortSize",
    "stale_after_seconds": "statistics.staleAfterSeconds",
    "max_buckets_per_request": "statistics.maxBucketsPerRequest",
    "bucket_retention_months": "statistics.bucketRetentionMonths",
    "wrapped_enabled": "statistics.wrapped.enabled",
}

_DESCRIPTIONS = {
    "timezone": "Time zone of statistic days (empty: the portal default); changing it requires a rebuild.",
    "first_day_of_week": "First day of statistic weeks (0 = Monday … 6 = Sunday).",
    "default_min_cohort_size": "Minimum contributors before a community value is shown (privacy floor).",
    "stale_after_seconds": "Seconds after which a statistic's data is shown as stale.",
    "max_buckets_per_request": "Maximum daily buckets one request may read (narrow the period otherwise).",
    "bucket_retention_months": "Months daily statistic buckets are kept.",
    "wrapped_enabled": "Generate periodic “Wrapped” recaps.",
}


def declare_statistics_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    defaults = StatisticsConfig()
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
    if HIDDEN_SECTIONS not in known:
        declare(
            scope="global",
            key=HIDDEN_SECTIONS,
            schema=list[str],
            default=[],
            user_overridable=True,
            owner=OWNER,
            description="Statistics sections I have hidden (only hideable ones).",
        )


declare_statistics_settings()
