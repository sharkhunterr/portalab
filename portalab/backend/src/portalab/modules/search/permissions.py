"""Search permissions (T002): ``search.use`` (granted to every user by default) and ``search.manage``
(reindex, status; audited)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:search"
SEARCH_USE = "search.use"
SEARCH_MANAGE = "search.manage"
SELF = "users.self.manage"


def declare_search_permissions(registry: PermissionRegistry = default_permissions) -> None:
    registry.declare(
        SEARCH_USE, "Use global search and the command palette search", default_roles=("user",), owner=OWNER
    )
    registry.declare(SEARCH_MANAGE, "Manage search indexing and settings", sensitive=True, owner=OWNER)


declare_search_permissions()
