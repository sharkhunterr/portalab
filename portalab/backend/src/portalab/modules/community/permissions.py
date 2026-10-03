"""Community permissions (T002): ``community.read``, ``community.propose`` and ``community.participate``
(granted to users), ``community.moderate`` and ``community.events.manage`` (moderators/Admin; sensitive,
audited). Voting is not a permission: it is the *active account* invariant (slice D)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:community"
READ = "community.read"
PROPOSE = "community.propose"
PARTICIPATE = "community.participate"
MODERATE = "community.moderate"
EVENTS_MANAGE = "community.events.manage"


def declare_community_permissions(registry: PermissionRegistry = default_permissions) -> None:
    for key, description, sensitive, roles in (
        (READ, "See the community: members, profiles, feed, events", False, ("user",)),
        (PROPOSE, "Propose community projects", False, ("user",)),
        (PARTICIPATE, "Participate in community projects", False, ("user",)),
        (MODERATE, "Moderate community proposals", True, ("moderator",)),
        (EVENTS_MANAGE, "Create and edit community events", True, ("moderator",)),
    ):
        if registry.get(key) is None:
            registry.declare(key, description, sensitive=sensitive, default_roles=roles, owner=OWNER)


declare_community_permissions()
