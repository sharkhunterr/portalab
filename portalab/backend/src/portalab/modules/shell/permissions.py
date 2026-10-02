"""Shell permissions (T003): ``shell.manage`` edits the admin navigation layout (sensitive, audited)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:shell"
SHELL_MANAGE = "shell.manage"
AUTHENTICATED = "users.self.manage"  # held by every signed-in account (base User role)


def declare_shell_permissions(registry: PermissionRegistry = default_permissions) -> None:
    registry.declare(SHELL_MANAGE, "Manage the portal navigation layout", sensitive=True, owner=OWNER)


declare_shell_permissions()
