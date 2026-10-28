"""Games permissions (issue 265): ``games.play`` — play, alone or in a party (default user grant);
``games.manage`` — set the games up, for the administrators."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:games"
PLAY = "games.play"
MANAGE = "games.manage"


def declare_games_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(PLAY) is None:
        registry.declare(PLAY, "Play the games, alone or in a party", default_roles=("user",), owner=OWNER)
    if registry.get(MANAGE) is None:
        registry.declare(MANAGE, "Set the games up", sensitive=True, owner=OWNER)


declare_games_permissions()
