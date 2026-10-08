"""Media permissions (T002): reading the catalog and requesting media are granted to every user; managing
identity (match/merge/split/overrides) is an audited Admin capability."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:media"
MEDIA_READ = "media.read"
MEDIA_REQUEST = "media.request"
MEDIA_MANAGE = "media.manage"
MEDIA_PLAY = "media.play"  # 027 (#2): watch in the portal's own player
# 027: the indexers' interactive search on a title's page — an advanced feature, unlocked per member (a
# Marketplace « access » product grants it); administrators have it
MEDIA_RELEASE_SEARCH = "media.release_search"
SELF = "users.self.manage"


def declare_media_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(MEDIA_READ) is None:
        registry.declare(MEDIA_READ, "Browse the media catalog", default_roles=("user",), owner=OWNER)
    if registry.get(MEDIA_REQUEST) is None:
        registry.declare(
            MEDIA_REQUEST, "Request media (within the quota)", default_roles=("user",), owner=OWNER
        )
    if registry.get(MEDIA_PLAY) is None:
        registry.declare(
            MEDIA_PLAY, "Watch films and series in the portal's player", default_roles=("user",), owner=OWNER
        )
    if registry.get(MEDIA_MANAGE) is None:
        registry.declare(
            MEDIA_MANAGE,
            "Manage media identity: matching, merge, split and field overrides",
            sensitive=True,
            owner=OWNER,
        )

    if registry.get(MEDIA_RELEASE_SEARCH) is None:
        registry.declare(
            MEDIA_RELEASE_SEARCH,
            "Search the indexers for a title's releases (advanced; unlocked in the shop)",
            user_grantable=True,
            owner=OWNER,
        )


declare_media_permissions()
