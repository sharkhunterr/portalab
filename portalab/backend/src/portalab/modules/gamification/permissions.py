"""Gamification permissions (T002): ``gamification.read`` (default user grant; other users' progression also
needs their visibility, 021); ``gamification.manage``, ``rewards.grant`` and ``economy.manage`` belong to the
core catalog (Admin, sensitive, audited)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:gamification"
READ = "gamification.read"
MANAGE = "gamification.manage"
GRANT = "rewards.grant"
ECONOMY_MANAGE = "economy.manage"


def declare_gamification_permissions(registry: PermissionRegistry = default_permissions) -> None:
    if registry.get(READ) is None:
        registry.declare(
            READ, "See progression, achievements and leaderboards", default_roles=("user",), owner=OWNER
        )


declare_gamification_permissions()
