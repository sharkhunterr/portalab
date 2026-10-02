"""Retention of the technical sync history (spec 021 engine, ``technical`` class window).

``sync_runs`` rows are immutable (UPDATE/TRUNCATE rejected by trigger); the only deletion is this windowed
retention delete, applied by the Privacy engine.
"""

from portalab.capabilities.retention import RetentionTarget, default_retention_targets

OWNER = "module:connectors"

SYNC_RUNS = RetentionTarget(
    "connectors.sync_runs", "connectors.sync_runs", "technical", "finished_at", "delete", OWNER
)


def register_targets() -> None:
    default_retention_targets.register(SYNC_RUNS)
