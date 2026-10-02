"""Observability permissions (T003): read for Support (redacted context) and Admin, manage audited."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:observability"
OBSERVABILITY_READ = "observability.read"
OBSERVABILITY_MANAGE = "observability.manage"


def declare_observability_permissions(registry: PermissionRegistry = default_permissions) -> None:
    registry.declare(
        OBSERVABILITY_READ,
        "View portal observability (Support sees redacted context)",
        default_roles=("support",),
        owner=OWNER,
    )
    registry.declare(
        OBSERVABILITY_MANAGE,
        "Acknowledge/resolve errors and validate/dismiss anomalies",
        sensitive=True,
        owner=OWNER,
    )


declare_observability_permissions()
