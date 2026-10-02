"""Administration permissions (T002), all sensitive (FR-019 of 003): every change is audited."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:administration"


def declare_admin_permissions(registry: PermissionRegistry = default_permissions) -> None:
    for key, description in (
        ("configuration.manage", "Change portal configuration and policies"),
        ("modules.manage", "Enable or disable modules"),
        ("plugins.manage", "Enable or disable plugins"),
        ("connectors.manage", "Enable or disable connectors and services"),
    ):
        registry.declare(key, description, sensitive=True, owner=OWNER)


declare_admin_permissions()
