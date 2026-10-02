"""i18n permissions (T003): ``i18n.manage`` edits translations and reads i18n health (audited)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:i18n"
I18N_MANAGE = "i18n.manage"
AUTHENTICATED = "users.self.manage"


def declare_i18n_permissions(registry: PermissionRegistry = default_permissions) -> None:
    registry.declare(I18N_MANAGE, "Manage translations and language settings", sensitive=True, owner=OWNER)


declare_i18n_permissions()
