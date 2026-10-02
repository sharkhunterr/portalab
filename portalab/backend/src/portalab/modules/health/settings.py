"""Health settings (T002), declared to Administration (CD-011)."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:health"


@dataclass(frozen=True, slots=True)
class HealthConfig:
    probe_interval_seconds: int = 60
    degraded_latency_ms: int = 1500
    unavailable_after_failures: int = 3
    stale_after_seconds: int = 300
    sample_retention_days: int = 14
    infra_retention_days: int = 14
    rollup_retention_months: int = 13
    section_timeout_seconds: float = 2.0


SETTINGS: dict[str, str] = {
    "probe_interval_seconds": "health.probeIntervalSeconds",
    "degraded_latency_ms": "health.degradedLatencyMs",
    "unavailable_after_failures": "health.unavailableAfterFailures",
    "stale_after_seconds": "health.staleAfterSeconds",
    "sample_retention_days": "health.sampleRetentionDays",
    "infra_retention_days": "health.infraRetentionDays",
    "rollup_retention_months": "health.rollupRetentionMonths",
}

_DESCRIPTIONS = {
    "probe_interval_seconds": "Seconds between health probes of a service.",
    "degraded_latency_ms": "Probe latency (ms) above which a service is Degraded.",
    "unavailable_after_failures": "Consecutive failed probes after which a service is Unavailable.",
    "stale_after_seconds": "Seconds without a probe after which the state is Unknown (never Operational).",
    "sample_retention_days": "Days raw health samples are kept.",
    "infra_retention_days": "Days infrastructure metric samples are kept.",
    "rollup_retention_months": "Months hourly availability rollups are kept.",
}


def declare_health_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    defaults = HealthConfig()
    for field, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, field)
            declare(
                scope="global",
                key=key,
                schema=type(default),
                default=default,
                owner=OWNER,
                description=_DESCRIPTIONS[field],
            )


declare_health_settings()
