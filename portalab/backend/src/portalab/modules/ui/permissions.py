"""UI permissions (T003): ``appearance.manage`` registers and enables themes (sensitive, audited)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:ui"
APPEARANCE_MANAGE = "appearance.manage"


def declare_ui_permissions(registry: PermissionRegistry = default_permissions) -> None:
    registry.declare(
        APPEARANCE_MANAGE,
        "Register, enable and disable portal themes",
        sensitive=True,
        owner=OWNER,
    )


declare_ui_permissions()
