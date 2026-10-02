"""Retention targets of the Events module (T024; FR-021/022): business and technical events are dropped by
month partition with their own windows (``events.retention.*``); deduplication keys and delivery records are
pruned row by row (mutable tables)."""

from collections.abc import Callable
from datetime import timedelta

from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.modules.events.settings import EventsConfig

OWNER = "module:events"


def register_targets(config: Callable[[], EventsConfig]) -> None:
    def months(value: int | None) -> timedelta | None:
        return timedelta(days=31 * value) if value else None

    def days(value: int | None) -> timedelta | None:
        return timedelta(days=value) if value else None

    for target in (
        RetentionTarget(
            "events.business",
            "events.events_business",
            "history",
            "occurred_at",
            "drop_partition",
            OWNER,
            window=lambda: months(config().business_retention_months),
        ),
        RetentionTarget(
            "events.technical",
            "events.events_technical",
            "technical",
            "occurred_at",
            "drop_partition",
            OWNER,
            window=lambda: days(config().technical_retention_days),
        ),
        RetentionTarget(
            "events.dedup_keys",
            "events.dedup_keys",
            "technical",
            "first_seen_at",
            "delete",
            OWNER,
            window=lambda: days(config().dedup_key_retention_days),
        ),
        RetentionTarget(
            "events.deliveries",
            "events.deliveries",
            "technical",
            "updated_at",
            "delete",
            OWNER,
            window=lambda: days(config().technical_retention_days),
            extra_condition="status IN ('succeeded', 'dead')",
        ),
    ):
        default_retention_targets.register(target)
