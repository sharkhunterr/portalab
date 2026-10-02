"""Events settings (T002), declared to Administration (CD-011)."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:events"


@dataclass(frozen=True, slots=True)
class EventsConfig:
    dispatch_batch_size: int = 200
    max_delivery_attempts: int = 8
    retry_backoff_seconds: int = 30
    business_retention_months: int | None = 60
    technical_retention_days: int | None = 30
    dedup_key_retention_days: int | None = 400
    dead_letter_alert_threshold: int = 1


def declare_events_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    defaults = EventsConfig()
    for key, schema, default, description in (
        (
            "events.dispatchBatchSize",
            int,
            defaults.dispatch_batch_size,
            "Events delivered per consumer batch.",
        ),
        ("events.maxDeliveryAttempts", int, defaults.max_delivery_attempts, "Attempts before a dead letter."),
        (
            "events.retryBackoff",
            int,
            defaults.retry_backoff_seconds,
            "Base delay (s) between delivery retries.",
        ),
        (
            "events.retention.business.months",
            int | None,
            defaults.business_retention_months,
            "Months business events are kept.",
        ),
        (
            "events.retention.technical.days",
            int | None,
            defaults.technical_retention_days,
            "Days technical events are kept.",
        ),
        (
            "events.dedupKeyRetention",
            int | None,
            defaults.dedup_key_retention_days,
            "Days deduplication keys are kept.",
        ),
        (
            "events.deadLetterAlertThreshold",
            int,
            defaults.dead_letter_alert_threshold,
            "Dead letters before a required action is raised.",
        ),
    ):
        if key not in known:
            declare(
                scope="global", key=key, schema=schema, default=default, owner=OWNER, description=description
            )


declare_events_settings()
