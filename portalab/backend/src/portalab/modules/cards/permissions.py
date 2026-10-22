"""Cards permissions (issue 229): ``cards.read`` — a member's own collection (default user grant);
``cards.manage`` — making the cards again, for the administrators."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:cards"
READ = "cards.read"
MANAGE = "cards.manage"


def declare_cards_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(READ) is None:
        registry.declare(READ, "Collect and see the media cards", default_roles=("user",), owner=OWNER)
    if registry.get(MANAGE) is None:
        registry.declare(MANAGE, "Make the media cards again", sensitive=True, owner=OWNER)


declare_cards_permissions()
