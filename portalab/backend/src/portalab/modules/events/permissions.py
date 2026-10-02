"""Events permissions (T003). ``events.manage`` is declared by the core catalog (spec 003, CD-033)."""

from portalab.core.permissions import PermissionRegistry, default_permissions

OWNER = "module:events"


def declare_events_permissions(registry: PermissionRegistry = default_permissions) -> None:
    registry.declare(
        "events.replay",
        "Rebuild projections from history",
        sensitive=True,
        requires_confirmation=True,
        owner=OWNER,
    )


declare_events_permissions()
