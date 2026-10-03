"""Plugin permissions (T002): ``plugins.read`` and ``plugins.purge`` (Admin; purge sensitive, confirmed,
audited). ``plugins.manage`` and ``modules.manage`` are declared by Administration (020 toggles)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:plugins"
READ = "plugins.read"
MANAGE = "plugins.manage"
PURGE = "plugins.purge"
MODULES = "modules.manage"


def declare_plugin_permissions(registry: PermissionRegistry = default_permissions) -> None:
    for key, description, sensitive in (
        (READ, "See installed plugins, their contributions and diagnostics", False),
        (PURGE, "Delete a plugin's data for good", True),
    ):
        if registry.get(key) is None:
            registry.declare(key, description, sensitive=sensitive, owner=OWNER)


declare_plugin_permissions()
