"""UI permissions (T003): ``appearance.manage`` registers and enables themes (sensitive, audited)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:ui"
APPEARANCE_MANAGE = "appearance.manage"
SITE_MANAGE = "site.manage"  # issue 159: the site's name, slogan, logo, icon and currency


def declare_ui_permissions(registry: PermissionRegistry = default_permissions) -> None:
    registry.declare(
        APPEARANCE_MANAGE,
        "Register, enable and disable portal themes",
        sensitive=True,
        owner=OWNER,
    )
    registry.declare(
        SITE_MANAGE,
        "Change the site's identity: its name, slogan, logo, icon and currency",
        sensitive=True,
        owner=OWNER,
    )


declare_ui_permissions()
