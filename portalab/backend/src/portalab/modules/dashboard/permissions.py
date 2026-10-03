"""Dashboard permissions (T002): ``dashboard.manage`` edits widget policies and the starter layout
(sensitive, audited). Users manage their own dashboard with ``users.self.manage``."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:dashboard"
DASHBOARD_MANAGE = "dashboard.manage"
SELF = "users.self.manage"


def declare_dashboard_permissions(registry: PermissionRegistry = default_permissions) -> None:
    registry.declare(
        DASHBOARD_MANAGE,
        "Manage dashboard widget policies and the starter layout",
        sensitive=True,
        owner=OWNER,
    )


declare_dashboard_permissions()
