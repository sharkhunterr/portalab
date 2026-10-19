"""Observability settings (T002), declared to Administration (CD-011). No threshold is hard-coded in the
evaluators or detectors: they read these values (FR-014)."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:observability"


@dataclass(frozen=True, slots=True)
class ObservabilityConfig:
    sample_retention_days: int = 14
    rollup_retention_months: int = 13
    error_retention_days: int = 90
    log_retention_days: int = 7  # issue 158: the log journal, by age…
    log_max_lines: int = 200_000  # … and by count
    escalation_auto_severity: str = "critical"
    escalation_require_validation: bool = True
    metrics_endpoint_enabled: bool = False
    # detectors
    error_spike_factor: float = 3.0
    error_spike_min_count: int = 5
    long_sync_factor: float = 3.0
    repeated_automation_threshold: int = 20
    stuck_consumer_minutes: int = 15
    latency_spike_factor: float = 3.0
    repeated_failure_count: int = 5
    # thresholds
    sync_stale_hours: int = 24
    events_lag_degraded: int = 1_000
    events_lag_failing: int = 10_000
    jobs_queued_age_minutes: int = 15
    jobs_failed_degraded: int = 1
    ai_failure_rate_degraded: float = 0.2
    db_latency_degraded_ms: int = 500
    slow_request_ms: int = 1_500


SETTINGS: dict[str, str] = {
    "sample_retention_days": "observability.sampleRetentionDays",
    "rollup_retention_months": "observability.rollupRetentionMonths",
    "error_retention_days": "observability.errorRetentionDays",
    "log_retention_days": "observability.logRetentionDays",
    "log_max_lines": "observability.logMaxLines",
    "escalation_auto_severity": "observability.escalation.autoSeverity",
    "escalation_require_validation": "observability.escalation.requireValidation",
    "metrics_endpoint_enabled": "observability.metricsEndpointEnabled",
    "error_spike_factor": "observability.detectors.errorSpike.factor",
    "error_spike_min_count": "observability.detectors.errorSpike.minCount",
    "long_sync_factor": "observability.detectors.longSync.factor",
    "repeated_automation_threshold": "observability.detectors.repeatedAutomation.threshold",
    "stuck_consumer_minutes": "observability.detectors.stuckConsumer.minutes",
    "latency_spike_factor": "observability.detectors.latencySpike.factor",
    "repeated_failure_count": "observability.detectors.repeatedFailure.count",
    "sync_stale_hours": "observability.thresholds.sync.staleHours",
    "events_lag_degraded": "observability.thresholds.events.lagDegraded",
    "events_lag_failing": "observability.thresholds.events.lagFailing",
    "jobs_queued_age_minutes": "observability.thresholds.jobs.queuedAgeMinutes",
    "jobs_failed_degraded": "observability.thresholds.jobs.failedDegraded",
    "ai_failure_rate_degraded": "observability.thresholds.ai.failureRate",
    "db_latency_degraded_ms": "observability.thresholds.db.latencyMs",
    "slow_request_ms": "observability.thresholds.performance.slowMs",
}
METRICS_TOKEN = "observability.metricsToken"  # noqa: S105 — a setting key, not a secret


def declare_observability_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    defaults = ObservabilityConfig()
    for name, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, name)
            schema = type(default)
            declare(
                scope="global",
                key=key,
                schema=schema,
                default=default,
                owner=OWNER,
                description=f"Observability: {name.replace('_', ' ')}.",
            )
    if METRICS_TOKEN not in known:
        declare(
            scope="global",
            key=METRICS_TOKEN,
            schema=str | None,
            default=None,
            sensitive=True,
            owner=OWNER,
            description="Bearer token accepted by the optional /metrics endpoint (write-only).",
        )


declare_observability_settings()
