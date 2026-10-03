"""Media permissions (T002): reading the catalog and requesting media are granted to every user; managing
identity (match/merge/split/overrides) is an audited Admin capability."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:media"
MEDIA_READ = "media.read"
MEDIA_REQUEST = "media.request"
MEDIA_MANAGE = "media.manage"
SELF = "users.self.manage"


def declare_media_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(MEDIA_READ) is None:
        registry.declare(MEDIA_READ, "Browse the media catalog", default_roles=("user",), owner=OWNER)
    if registry.get(MEDIA_REQUEST) is None:
        registry.declare(
            MEDIA_REQUEST, "Request media (within the quota)", default_roles=("user",), owner=OWNER
        )
    if registry.get(MEDIA_MANAGE) is None:
        registry.declare(
            MEDIA_MANAGE,
            "Manage media identity: matching, merge, split and field overrides",
            sensitive=True,
            owner=OWNER,
        )


declare_media_permissions()
