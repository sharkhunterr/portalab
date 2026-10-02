"""Retention (T003/T031; FR-026..028): detailed minute samples expire first (monthly partitions dropped),
rollups live for months, resolved errors are deleted after their window; all technical class (021)."""

from collections.abc import Callable
from datetime import timedelta

from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.modules.observability.settings import ObservabilityConfig

OWNER = "module:observability"


def register_targets(config: Callable[[], ObservabilityConfig]) -> None:
    for target in (
        RetentionTarget(
            "observability.samples",
            "obs.metric_samples",
            "technical",
            "sampled_at",
            "drop_partition",
            OWNER,
            window=lambda: timedelta(days=config().sample_retention_days),
        ),
        RetentionTarget(
            "observability.rollups",
            "obs.rollups",
            "technical",
            "bucket",
            "delete",
            OWNER,
            window=lambda: timedelta(days=31 * config().rollup_retention_months),
        ),
        RetentionTarget(
            "observability.errors",
            "obs.errors",
            "technical",
            "last_seen_at",
            "delete",
            OWNER,
            extra_condition="state = 'resolved'",
            window=lambda: timedelta(days=config().error_retention_days),
        ),
        RetentionTarget(
            "observability.anomalies",
            "obs.anomalies",
            "technical",
            "last_seen_at",
            "delete",
            OWNER,
            extra_condition="status IN ('dismissed', 'resolved', 'escalated')",
            window=lambda: timedelta(days=config().error_retention_days),
        ),
    ):
        default_retention_targets.register(target)
