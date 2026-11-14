"""Retro permissions (issue 419): ``retro.play`` — play a library's games in the portal (a user's grant)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:retro"
PLAY = "retro.play"


def declare_retro_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(PLAY) is None:
        registry.declare(PLAY, "Play a library's games in the portal", default_roles=("user",), owner=OWNER)


declare_retro_permissions()
