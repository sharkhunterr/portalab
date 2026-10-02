"""Privacy permissions (T003). ``audit.read`` is declared by the core catalog (spec 003)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:privacy"


def declare_privacy_permissions(registry: PermissionRegistry = default_permissions) -> None:
    registry.declare(
        "privacy.manage", "Apply visibility policies and change retention", sensitive=True, owner=OWNER
    )
    registry.declare(
        "services.purge",
        "Purge the historized data of a service",
        sensitive=True,
        requires_confirmation=True,
        owner=OWNER,
    )


declare_privacy_permissions()
