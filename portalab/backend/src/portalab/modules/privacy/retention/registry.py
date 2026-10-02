"""Kernel and privacy retention targets (T007). The registry itself is the capability-layer contract
(:mod:`portalab.capabilities.retention`) so any module may declare targets without importing privacy."""

from portalab.capabilities.retention import RetentionTarget, default_retention_targets

OWNER = "module:privacy"

AUDIT_TARGET = "audit.audit_entries"


def register_kernel_targets() -> None:
    for target in (
        RetentionTarget(
            name="core.live_event",
            table="core.live_event",
            data_class="technical",
            timestamp_column="created_at",
            action="delete",
            owner=OWNER,
        ),
        RetentionTarget(
            name="core.job.finished",
            table="core.job",
            data_class="technical",
            timestamp_column="updated_at",
            action="delete",
            owner=OWNER,
            extra_condition="status IN ('succeeded', 'dead')",
        ),
        RetentionTarget(
            name=AUDIT_TARGET,
            table="audit.audit_entries",
            data_class="audit",
            timestamp_column="occurred_at",
            action="drop_partition",
            owner=OWNER,
        ),
    ):
        default_retention_targets.register(target)


register_kernel_targets()
