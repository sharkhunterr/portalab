"""Retention targets (T003; spec 021 engine): raw and infrastructure samples are technical data thinned
by dropping monthly partitions; rollups and recent errors are deleted past their windows. State history is
kept (it is small and backs availability)."""

from collections.abc import Callable
from datetime import timedelta

from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.modules.health.settings import HealthConfig

OWNER = "module:health"


def register_targets(config: Callable[[], HealthConfig]) -> None:
    for target in (
        RetentionTarget(
            "health.samples",
            "health.health_samples",
            "technical",
            "checked_at",
            "drop_partition",
            OWNER,
            window=lambda: timedelta(days=config().sample_retention_days),
        ),
        RetentionTarget(
            "health.infra_samples",
            "health.infra_samples",
            "technical",
            "sampled_at",
            "drop_partition",
            OWNER,
            window=lambda: timedelta(days=config().infra_retention_days),
        ),
        RetentionTarget(
            "health.rollups",
            "health.health_rollups",
            "technical",
            "bucket_start",
            "delete",
            OWNER,
            window=lambda: timedelta(days=31 * config().rollup_retention_months),
        ),
        RetentionTarget(
            "health.recent_errors",
            "health.recent_errors",
            "technical",
            "last_seen_at",
            "delete",
            OWNER,
            window=lambda: timedelta(days=config().sample_retention_days),
        ),
    ):
        default_retention_targets.register(target)
